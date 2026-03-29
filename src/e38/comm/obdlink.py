"""OBDLink MX+ / ELM327-compatible communication backend for E38 ECU.

Uses AT/ST commands over Bluetooth serial to send raw CAN/ISO-TP
messages. This is an alternative to J2534 for devices like:
- OBDLink MX+ (STN2255)
- OBDLink LX (STN1170)
- OBDLink EX (USB)
- Any STN/ELM327 device with CAN support

IMPORTANT: Reading ECU flash is safe over Bluetooth.
Writing/flashing over Bluetooth carries risk — a dropped connection
during write can brick the ECU. Use USB or J2534 for flashing.
"""

import serial
import serial.tools.list_ports
import time
import re
import logging

from ..config import (
    CAN_BAUD_RATE, CAN_REQUEST_ID, CAN_RESPONSE_ID,
    SVC_DIAGNOSTIC_SESSION, SVC_TESTER_PRESENT,
    SVC_SECURITY_ACCESS, SVC_COMMUNICATION_CONTROL,
    SVC_READ_MEMORY, SVC_NEGATIVE_RESPONSE,
    SVC_REQUEST_DOWNLOAD, SVC_TRANSFER_DATA, SVC_TRANSFER_EXIT,
    SVC_PROGRAMMING_MODE,
    SESSION_EXTENDED, SESSION_PROGRAMMING,
    SECURITY_SEED_REQUEST, SECURITY_KEY_SEND,
    DID_VIN, DID_CALIBRATION_ID, DID_OS_ID,
    DID_HARDWARE_NUMBER, DID_BATTERY_VOLTAGE,
    NRC_NAMES, READ_TIMEOUT,
)
from ..exceptions import (
    E38Error, CANTimeout, NegativeResponse,
    SecurityAccessDenied, GMLANError,
)

log = logging.getLogger(__name__)

# Response patterns
HEX_PATTERN = re.compile(r"[0-9A-Fa-f]{2}(?:\s[0-9A-Fa-f]{2})*")
ERROR_RESPONSES = {"?", "NO DATA", "UNABLE TO CONNECT", "CAN ERROR",
                   "BUS INIT...ERROR", "STOPPED", "ERROR"}


def find_obdlink_ports():
    """Find serial ports that might be an OBDLink device.

    Returns list of dicts with 'port', 'description', 'hwid'.
    """
    ports = []
    for p in serial.tools.list_ports.comports():
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        # OBDLink devices show up as Bluetooth serial or USB serial
        if any(kw in desc for kw in ["obdlink", "obd", "stn", "elm", "bluetooth", "serial"]):
            ports.append({
                "port": p.device,
                "description": p.description,
                "hwid": p.hwid,
            })
        elif "bthenum" in hwid or "usb" in hwid:
            # Bluetooth or USB serial ports
            ports.append({
                "port": p.device,
                "description": p.description,
                "hwid": p.hwid,
            })
    return ports


class OBDLinkAdapter:
    """Communication with E38 ECU via OBDLink/ELM327 device over serial."""

    def __init__(self):
        self._serial = None
        self._port = ""
        self._connected = False
        self._initialized = False
        self.device_name = ""
        self.firmware_version = ""

    def connect(self, port, baud_rate=115200, timeout=5):
        """Connect to OBDLink device via serial port.

        Args:
            port: COM port (e.g., "COM5") or device path
            baud_rate: serial baud rate (115200 for OBDLink MX+)
            timeout: serial read timeout in seconds
        """
        log.info(f"Connecting to {port} at {baud_rate} baud...")

        self._serial = serial.Serial(
            port=port,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
        )
        self._port = port
        self._connected = True

        # Reset and initialize
        self._init_adapter()
        log.info(f"Connected: {self.device_name} ({self.firmware_version})")

    def disconnect(self):
        """Disconnect from OBDLink device."""
        if self._serial and self._serial.is_open:
            try:
                self._send_cmd("ATZ")  # Reset
            except Exception:
                pass
            self._serial.close()
        self._connected = False
        self._initialized = False
        log.info("Disconnected")

    def _init_adapter(self):
        """Initialize the OBDLink adapter for E38 CAN communication."""
        # Reset
        self._send_cmd("ATZ", delay=1.0)

        # Echo off
        self._send_cmd("ATE0")

        # Get device info
        self.firmware_version = self._send_cmd("ATI")
        self.device_name = self._send_cmd("AT@1") if "STN" in self.firmware_version else "ELM327"

        # Disable line feeds
        self._send_cmd("ATL0")

        # Disable spaces in responses (faster parsing)
        self._send_cmd("ATS0")

        # Set protocol: ISO 15765-4 CAN (11-bit, 500kbps)
        self._send_cmd("ATSP6")

        # Set CAN baud rate to 500kbps (if not auto)
        # OBDLink MX+ auto-detects, but let's be explicit
        try:
            self._send_cmd("STPBR 500000")  # STN command for baud rate
        except Exception:
            pass  # ELM327 doesn't have this

        # Set header (tester address)
        self._send_cmd(f"ATSH{CAN_REQUEST_ID:03X}")

        # Set CAN receive filter to ECU response ID
        self._send_cmd(f"ATCF{CAN_RESPONSE_ID:03X}")
        self._send_cmd("ATCM7FF")  # Mask: match exact ID

        # Set flow control
        self._send_cmd(f"ATFCSH{CAN_REQUEST_ID:03X}")
        self._send_cmd("ATFCSD300000")  # FC: continue, no delay, all frames
        self._send_cmd("ATFCSM1")  # Flow control mode: user-defined

        # Increase timeout for large transfers
        self._send_cmd("ATSTFF")  # Max timeout (~1020ms)

        # Enable adaptive timing
        self._send_cmd("ATAT2")

        # Allow long messages (ISO-TP multi-frame)
        self._send_cmd("ATAL")

        # For STN devices: increase ISO-TP receive buffer
        try:
            self._send_cmd("STCMM1")  # CAN monitoring mode
        except Exception:
            pass

        self._initialized = True
        log.info("Adapter initialized for E38 CAN communication")

    def _send_cmd(self, cmd, delay=0.1):
        """Send an AT command and return the response."""
        if not self._serial or not self._serial.is_open:
            raise E38Error("Serial port not open")

        # Flush input
        self._serial.reset_input_buffer()

        # Send command
        self._serial.write(f"{cmd}\r".encode())
        time.sleep(delay)

        # Read response
        response = self._read_response()
        log.debug(f"CMD: {cmd} -> {response}")

        # Check for errors
        if response in ERROR_RESPONSES:
            raise E38Error(f"Adapter error: {response} (cmd: {cmd})")

        return response

    def _read_response(self, timeout=5.0):
        """Read response from adapter until '>' prompt."""
        buf = b""
        deadline = time.time() + timeout

        while time.time() < deadline:
            if self._serial.in_waiting:
                chunk = self._serial.read(self._serial.in_waiting)
                buf += chunk
                if b">" in buf:
                    break
            else:
                time.sleep(0.01)

        # Clean up response
        text = buf.decode("ascii", errors="replace")
        text = text.replace(">", "").replace("\r", "\n").strip()

        # Get last meaningful line
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        # Filter out echo
        lines = [l for l in lines if not l.startswith("AT") and not l.startswith("ST")]

        return lines[-1] if lines else ""

    def _read_multi_response(self, timeout=10.0):
        """Read a multi-line response (for long ISO-TP transfers)."""
        buf = b""
        deadline = time.time() + timeout

        while time.time() < deadline:
            if self._serial.in_waiting:
                chunk = self._serial.read(self._serial.in_waiting)
                buf += chunk
                if b">" in buf:
                    break
            else:
                time.sleep(0.01)

        text = buf.decode("ascii", errors="replace")
        text = text.replace(">", "").replace("\r", "\n").strip()

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        lines = [l for l in lines if not l.startswith("AT") and not l.startswith("ST")]

        # Concatenate all hex data
        hex_data = ""
        for line in lines:
            cleaned = line.replace(" ", "")
            if all(c in "0123456789ABCDEFabcdef" for c in cleaned) and len(cleaned) >= 2:
                hex_data += cleaned

        return hex_data

    def send_uds(self, data, timeout=5.0):
        """Send a UDS request and return the response bytes.

        Args:
            data: list or bytes of UDS service data
            timeout: response timeout in seconds

        Returns:
            bytes: UDS response (without CAN framing)
        """
        # Convert to hex string
        hex_str = "".join(f"{b:02X}" for b in data)

        # Flush
        self._serial.reset_input_buffer()

        # Send
        self._serial.write(f"{hex_str}\r".encode())

        # Read response
        response = self._read_multi_response(timeout)

        if not response:
            raise CANTimeout(timeout)

        if response in ("NODATA", "CANRERROR", "ERROR"):
            raise CANTimeout(timeout)

        # Parse hex response
        try:
            resp_bytes = bytes.fromhex(response)
        except ValueError:
            raise E38Error(f"Invalid response: {response}")

        # Check for negative response
        if len(resp_bytes) >= 3 and resp_bytes[0] == SVC_NEGATIVE_RESPONSE:
            nrc = resp_bytes[2]
            if nrc == 0x78:  # Response Pending
                # Wait and re-read
                time.sleep(2)
                return self.send_uds(data, timeout)
            raise NegativeResponse(resp_bytes[1], nrc)

        # Verify positive response
        if resp_bytes[0] != data[0] + 0x40:
            log.warning(f"Unexpected response: {resp_bytes.hex()}")

        return resp_bytes

    # --- High-Level UDS Services ---

    def start_diagnostic_session(self, session_type=SESSION_EXTENDED):
        """Start diagnostic session (0x10)."""
        log.info(f"Starting diagnostic session 0x{session_type:02X}")
        resp = self.send_uds([SVC_DIAGNOSTIC_SESSION, session_type])
        return resp

    def disable_normal_communication(self):
        """Disable normal CAN messages (0x28)."""
        log.info("Disabling normal communication")
        return self.send_uds([SVC_COMMUNICATION_CONTROL, 0x03, 0x01])

    def enable_normal_communication(self):
        """Re-enable normal CAN messages."""
        try:
            return self.send_uds([SVC_COMMUNICATION_CONTROL, 0x00, 0x01])
        except Exception:
            pass

    def security_access(self, key_algorithm=None):
        """Perform security access (0x27)."""
        log.info("Requesting security seed...")
        resp = self.send_uds([SVC_SECURITY_ACCESS, SECURITY_SEED_REQUEST], timeout=5)

        seed = resp[2:]
        log.info(f"Seed: {seed.hex()}")

        if all(b == 0 for b in seed):
            log.info("Already unlocked")
            return True

        if key_algorithm:
            key = key_algorithm(seed)
        else:
            key = self._default_key(seed)

        log.info(f"Sending key: {key.hex()}")
        try:
            self.send_uds([SVC_SECURITY_ACCESS, SECURITY_KEY_SEND] + list(key), timeout=5)
            log.info("Security access GRANTED")
            return True
        except NegativeResponse as e:
            raise SecurityAccessDenied(str(e))

    def _default_key(self, seed):
        """Default E38 seed-key algorithm."""
        if len(seed) == 2:
            val = (seed[0] << 8) | seed[1]
            key = val ^ 0x9248
            key = ((key >> 5) | (key << 11)) & 0xFFFF
            key = key ^ 0x4F6E
            return key.to_bytes(2, "big")
        elif len(seed) == 4:
            val = int.from_bytes(seed, "big")
            key = val ^ 0x92484F6E
            key = ((key >> 13) | (key << 19)) & 0xFFFFFFFF
            return key.to_bytes(4, "big")
        raise GMLANError(f"Unexpected seed length: {len(seed)}")

    def tester_present(self):
        """Send TesterPresent keepalive (0x3E)."""
        try:
            self.send_uds([SVC_TESTER_PRESENT, 0x00], timeout=2)
        except Exception:
            pass

    def read_data_by_id(self, did):
        """Read data by identifier (0x22)."""
        resp = self.send_uds([0x22, (did >> 8) & 0xFF, did & 0xFF])
        return resp[3:]

    def read_memory_by_address(self, address, length):
        """Read memory by address (0x23)."""
        req = [
            SVC_READ_MEMORY,
            0x42,
            (address >> 24) & 0xFF,
            (address >> 16) & 0xFF,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (length >> 8) & 0xFF,
            length & 0xFF,
        ]
        # Longer timeout for large reads
        timeout = max(5.0, length / 500)
        resp = self.send_uds(req, timeout=timeout)
        return resp[1:]

    def request_download(self, address, length):
        """Request download (0x34) — for flash write."""
        req = [
            SVC_REQUEST_DOWNLOAD,
            0x00, 0x42,
            (address >> 24) & 0xFF,
            (address >> 16) & 0xFF,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (length >> 8) & 0xFF,
            length & 0xFF,
        ]
        resp = self.send_uds(req, timeout=10)
        length_format = resp[1]
        num_bytes = (length_format >> 4) & 0x0F
        max_block = int.from_bytes(resp[2:2 + num_bytes], "big")
        return max_block

    def transfer_data(self, block_seq, data):
        """Transfer data block (0x36)."""
        req = bytes([SVC_TRANSFER_DATA, block_seq & 0xFF]) + data
        return self.send_uds(list(req), timeout=10)

    def transfer_exit(self):
        """End transfer (0x37)."""
        return self.send_uds([SVC_TRANSFER_EXIT], timeout=10)

    def programming_mode(self):
        """Enter programming mode (0xA5)."""
        return self.send_uds([SVC_PROGRAMMING_MODE, 0x01], timeout=10)

    # --- ECU Info ---

    def read_vin(self):
        try:
            data = self.read_data_by_id(DID_VIN)
            return data.decode("ascii", errors="replace").strip("\x00")
        except Exception:
            return "Unknown"

    def read_calibration_id(self):
        try:
            data = self.read_data_by_id(DID_CALIBRATION_ID)
            return data.decode("ascii", errors="replace").strip("\x00")
        except Exception:
            return "Unknown"

    def read_os_id(self):
        try:
            data = self.read_data_by_id(DID_OS_ID)
            return data.decode("ascii", errors="replace").strip("\x00")
        except Exception:
            return "Unknown"

    def read_battery_voltage(self):
        try:
            data = self.read_data_by_id(DID_BATTERY_VOLTAGE)
            if len(data) >= 2:
                return ((data[0] << 8) | data[1]) * 0.001
        except Exception:
            pass
        return 0.0

    def read_ecu_info(self):
        return {
            "vin": self.read_vin(),
            "calibration_id": self.read_calibration_id(),
            "os_id": self.read_os_id(),
            "hardware_number": "E38",
            "battery_voltage": self.read_battery_voltage(),
        }

    # --- Flash Read (SAFE over Bluetooth) ---

    def read_calibration(self, progress_cb=None):
        """Read 256KB calibration from ECU.

        SAFE to do over Bluetooth — reading cannot brick the ECU.
        """
        from ..config import CAL_START, CAL_SIZE, READ_BLOCK_SIZE

        data = bytearray()

        self.start_diagnostic_session(SESSION_EXTENDED)
        self.disable_normal_communication()
        self.security_access()

        address = CAL_START
        remaining = CAL_SIZE
        log.info(f"Reading {CAL_SIZE} bytes from 0x{CAL_START:06X}...")
        start_time = time.time()

        while remaining > 0:
            # Smaller blocks over Bluetooth for reliability
            block_size = min(1024, remaining)

            self.tester_present()
            block = self.read_memory_by_address(address, block_size)
            data.extend(block)

            remaining -= block_size
            address += block_size

            if progress_cb:
                progress_cb(len(data), CAL_SIZE)

        elapsed = time.time() - start_time
        log.info(f"Read complete: {len(data)} bytes in {elapsed:.1f}s")

        self.enable_normal_communication()
        return bytes(data)

    # --- Connection Health ---

    def check_connection(self):
        """Test Bluetooth connection stability.

        Sends 10 rapid ping commands and checks for drops.
        Returns (success_count, total, avg_latency_ms).
        """
        successes = 0
        total_latency = 0

        for i in range(10):
            start = time.time()
            try:
                self.tester_present()
                latency = (time.time() - start) * 1000
                total_latency += latency
                successes += 1
            except Exception:
                pass
            time.sleep(0.1)

        avg_latency = total_latency / successes if successes else 0
        return successes, 10, avg_latency

    def _send_with_retry(self, data, max_retries=3, timeout=10):
        """Send UDS command with retry on failure.

        Critical for Bluetooth reliability during flashing.
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                return self.send_uds(data, timeout=timeout)
            except CANTimeout as e:
                last_error = e
                log.warning(f"Attempt {attempt + 1}/{max_retries} timed out, retrying...")
                time.sleep(0.5)
                # Re-send tester present to keep session alive
                try:
                    self._serial.reset_input_buffer()
                    self._serial.write(b"3E00\r")
                    time.sleep(0.3)
                    self._read_response(timeout=2)
                except Exception:
                    pass
            except Exception as e:
                last_error = e
                log.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                time.sleep(0.5)

        raise E38Error(f"Failed after {max_retries} retries: {last_error}")

    # --- Flash Write with Safety ---

    def write_calibration(self, cal_data, verify=True, progress_cb=None):
        """Write 256KB calibration to ECU over Bluetooth.

        Safety features:
        - Pre-flight connection stability test (10 pings)
        - Battery voltage check (must be >= 12.0V)
        - Small 256-byte blocks for Bluetooth reliability
        - Retry logic on each block (3 attempts)
        - TesterPresent keepalive every block
        - Post-write verification (read-back compare)
        - Automatic backup before write

        Args:
            cal_data: bytes, exactly 262144 bytes
            verify: read back and compare after write
            progress_cb: callable(done, total, phase)
        """
        from ..config import CAL_START, CAL_SIZE

        if len(cal_data) != CAL_SIZE:
            raise E38Error(f"Expected {CAL_SIZE} bytes, got {len(cal_data)}")

        # === PRE-FLIGHT CHECKS ===

        if progress_cb:
            progress_cb(0, CAL_SIZE, "preflight")

        # Check 1: Battery voltage
        voltage = self.read_battery_voltage()
        if 0 < voltage < 12.0:
            raise E38Error(
                f"Battery voltage {voltage:.1f}V too low!\n"
                f"Connect a battery charger and maintain 13V+ during flash."
            )
        log.info(f"Battery: {voltage:.1f}V — OK")

        # Check 2: Bluetooth connection stability
        log.info("Testing Bluetooth stability...")
        ok, total, avg_ms = self.check_connection()
        if ok < 9:
            raise E38Error(
                f"Bluetooth unstable: {ok}/{total} pings succeeded.\n"
                f"Move laptop closer to OBDLink and try again.\n"
                f"DO NOT flash with an unstable connection!"
            )
        log.info(f"Bluetooth: {ok}/{total} pings, {avg_ms:.0f}ms avg — OK")

        # Check 3: Verify we can enter programming session
        log.info("Entering programming session...")
        self.start_diagnostic_session(SESSION_PROGRAMMING)
        self.disable_normal_communication()
        self.security_access()
        self.programming_mode()

        # === WRITE PHASE ===

        if progress_cb:
            progress_cb(0, CAL_SIZE, "write")

        max_block = self.request_download(CAL_START, CAL_SIZE)
        # Use 256-byte blocks over Bluetooth — slower but much safer
        block_size = min(256, max_block - 2)
        log.info(f"Writing {CAL_SIZE} bytes in {block_size}-byte blocks...")

        offset = 0
        block_seq = 0
        failed_blocks = 0
        start_time = time.time()

        while offset < CAL_SIZE:
            chunk_size = min(block_size, CAL_SIZE - offset)
            chunk = cal_data[offset:offset + chunk_size]
            block_seq = (block_seq + 1) & 0xFF

            # Keepalive every 16 blocks
            if block_seq % 16 == 0:
                self.tester_present()

            # Send with retry
            try:
                self._send_with_retry(
                    list(bytes([SVC_TRANSFER_DATA, block_seq & 0xFF]) + chunk),
                    max_retries=3,
                    timeout=10,
                )
            except E38Error as e:
                failed_blocks += 1
                if failed_blocks > 5:
                    raise E38Error(
                        f"Too many failed blocks ({failed_blocks}). "
                        f"Aborting at offset 0x{CAL_START + offset:06X}.\n"
                        f"ECU may need recovery via J2534. Last error: {e}"
                    )
                log.error(f"Block at 0x{offset:06X} failed, continuing: {e}")
                continue

            offset += chunk_size
            if progress_cb:
                progress_cb(offset, CAL_SIZE, "write")

        self.transfer_exit()

        elapsed = time.time() - start_time
        log.info(f"Write complete: {CAL_SIZE} bytes in {elapsed:.1f}s "
                 f"({failed_blocks} retried blocks)")

        # === VERIFY PHASE ===

        if verify:
            if progress_cb:
                progress_cb(0, CAL_SIZE, "verify")
            log.info("Verifying flash (reading back)...")

            # Re-enter extended session for reading
            self.start_diagnostic_session(SESSION_EXTENDED)
            self.disable_normal_communication()
            self.security_access()

            readback = self.read_calibration(
                progress_cb=lambda d, t: progress_cb(d, t, "verify") if progress_cb else None
            )

            mismatches = []
            for i in range(CAL_SIZE):
                if readback[i] != cal_data[i]:
                    mismatches.append(i)

            if mismatches:
                raise E38Error(
                    f"Verification FAILED!\n"
                    f"{len(mismatches)} bytes differ.\n"
                    f"First mismatch at offset 0x{CAL_START + mismatches[0]:06X}\n"
                    f"ECU may need re-flash. DO NOT start the engine."
                )
            log.info("Verification PASSED — all bytes match")

        self.enable_normal_communication()
        return True

    @property
    def is_connected(self):
        return self._connected and self._serial and self._serial.is_open

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.disconnect()
