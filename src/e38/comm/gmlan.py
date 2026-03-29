"""GMLAN diagnostic service layer for E38 ECU.

Implements UDS-based diagnostic services over ISO 15765 (CAN).
"""

import time
import logging
import threading

from ..config import (
    SVC_DIAGNOSTIC_SESSION, SVC_ECU_RESET, SVC_READ_DATA_BY_ID,
    SVC_READ_MEMORY, SVC_SECURITY_ACCESS, SVC_COMMUNICATION_CONTROL,
    SVC_REQUEST_DOWNLOAD, SVC_TRANSFER_DATA, SVC_TRANSFER_EXIT,
    SVC_TESTER_PRESENT, SVC_PROGRAMMING_MODE, SVC_NEGATIVE_RESPONSE,
    SESSION_DEFAULT, SESSION_EXTENDED, SESSION_PROGRAMMING,
    SECURITY_SEED_REQUEST, SECURITY_KEY_SEND,
    DID_VIN, DID_CALIBRATION_ID, DID_OS_ID, DID_ECU_SERIAL,
    DID_BATTERY_VOLTAGE, DID_HARDWARE_NUMBER, DID_SOFTWARE_NUMBER,
    TESTER_PRESENT_INTERVAL, READ_TIMEOUT, WRITE_TIMEOUT,
)
from ..exceptions import (
    NegativeResponse, CANTimeout, SecurityAccessDenied, GMLANError,
)
from .j2534 import J2534

log = logging.getLogger(__name__)


class GMLAN:
    """GMLAN/UDS diagnostic service interface for E38 ECU."""

    def __init__(self, j2534: J2534):
        self._j2534 = j2534
        self._tester_thread = None
        self._tester_running = False

    def _request(self, data, timeout_ms=2000, expect_response=True):
        """Send a UDS request and return the response.

        Handles 0x78 (response pending) by waiting and re-reading.
        """
        self._j2534.clear_buffers()
        self._j2534.send(bytes(data), timeout_ms)

        if not expect_response:
            return None

        deadline = time.time() + (timeout_ms / 1000) + 30  # extra time for pending
        while time.time() < deadline:
            resp = self._j2534.receive(timeout_ms)
            if resp is None:
                raise CANTimeout(timeout_ms / 1000)

            # Negative response
            if resp[0] == SVC_NEGATIVE_RESPONSE:
                nrc = resp[2] if len(resp) > 2 else 0
                if nrc == 0x78:  # Response Pending
                    log.debug("ECU: Response Pending, waiting...")
                    time.sleep(1)
                    continue
                raise NegativeResponse(resp[1], nrc)

            # Positive response (service ID + 0x40)
            if resp[0] == data[0] + 0x40:
                return resp

            log.warning(f"Unexpected response: {resp.hex()}")

        raise CANTimeout(timeout_ms / 1000)

    # --- Session Management ---

    def start_diagnostic_session(self, session_type=SESSION_EXTENDED):
        """Start a diagnostic session (service 0x10)."""
        log.info(f"Starting diagnostic session type 0x{session_type:02X}")
        resp = self._request([SVC_DIAGNOSTIC_SESSION, session_type])
        log.info(f"Diagnostic session active: 0x{resp[1]:02X}")
        return resp

    def start_programming_session(self):
        """Enter programming session for flash operations."""
        return self.start_diagnostic_session(SESSION_PROGRAMMING)

    def ecu_reset(self, reset_type=0x01):
        """Reset ECU (service 0x11). Type 0x01 = hard reset."""
        log.info(f"Resetting ECU (type 0x{reset_type:02X})")
        try:
            self._request([SVC_ECU_RESET, reset_type], expect_response=False)
        except Exception:
            pass  # ECU may not respond after reset

    # --- Communication Control ---

    def disable_normal_communication(self):
        """Disable normal CAN communication (service 0x28).
        Required before security access and flashing.
        """
        log.info("Disabling normal communication")
        return self._request([SVC_COMMUNICATION_CONTROL, 0x03, 0x01])

    def enable_normal_communication(self):
        """Re-enable normal CAN communication."""
        log.info("Enabling normal communication")
        try:
            return self._request([SVC_COMMUNICATION_CONTROL, 0x00, 0x01])
        except Exception:
            pass

    # --- Security Access ---

    def security_access(self, key_algorithm=None):
        """Perform security access handshake (service 0x27).

        Args:
            key_algorithm: callable(seed_bytes) -> key_bytes, or None for default
        """
        log.info("Requesting security seed...")
        resp = self._request([SVC_SECURITY_ACCESS, SECURITY_SEED_REQUEST], timeout_ms=5000)

        # Extract seed (skip service + sub-function bytes)
        seed = resp[2:]
        log.info(f"Seed received: {seed.hex()}")

        if all(b == 0 for b in seed):
            log.info("ECU already unlocked (zero seed)")
            return True

        # Calculate key
        if key_algorithm:
            key = key_algorithm(seed)
        else:
            key = self._default_key_algorithm(seed)

        log.info(f"Sending key: {key.hex()}")
        try:
            resp = self._request(
                [SVC_SECURITY_ACCESS, SECURITY_KEY_SEND] + list(key),
                timeout_ms=5000
            )
            log.info("Security access GRANTED")
            return True
        except NegativeResponse as e:
            if e.nrc in (0x33, 0x35, 0x36):
                raise SecurityAccessDenied(f"Security access failed: {e}")
            raise

    def _default_key_algorithm(self, seed):
        """Default E38 seed-key algorithm.

        The E38 uses a simple XOR-based algorithm for most calibrations.
        """
        if len(seed) == 2:
            seed_val = (seed[0] << 8) | seed[1]
            # Algorithm 0x92 — common E38 key derivation
            key_val = seed_val ^ 0x9248
            key_val = ((key_val >> 5) | (key_val << 11)) & 0xFFFF
            key_val = key_val ^ 0x4F6E
            return key_val.to_bytes(2, "big")
        elif len(seed) == 4:
            seed_val = int.from_bytes(seed, "big")
            key_val = seed_val ^ 0x92484F6E
            key_val = ((key_val >> 13) | (key_val << 19)) & 0xFFFFFFFF
            return key_val.to_bytes(4, "big")
        else:
            raise GMLANError(f"Unexpected seed length: {len(seed)}")

    # --- Data Reading ---

    def read_data_by_id(self, did):
        """Read data by identifier (service 0x22)."""
        resp = self._request([
            SVC_READ_DATA_BY_ID,
            (did >> 8) & 0xFF,
            did & 0xFF,
        ])
        return resp[3:]  # Skip service + DID echo

    def read_memory_by_address(self, address, length):
        """Read memory by address (service 0x23).

        Uses 4-byte address + 2-byte length format (addressAndLengthFormatIdentifier = 0x42).
        """
        req = [
            SVC_READ_MEMORY,
            0x42,  # 4 bytes address, 2 bytes length
            (address >> 24) & 0xFF,
            (address >> 16) & 0xFF,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (length >> 8) & 0xFF,
            length & 0xFF,
        ]
        resp = self._request(req, timeout_ms=int(READ_TIMEOUT * 1000))
        return resp[1:]  # Skip positive response byte

    # --- Flash Operations ---

    def request_download(self, address, length):
        """Request download to ECU (service 0x34).

        Tells ECU we're about to write data.
        """
        req = [
            SVC_REQUEST_DOWNLOAD,
            0x00,  # dataFormatIdentifier (no compression/encryption)
            0x42,  # addressAndLengthFormatIdentifier
            (address >> 24) & 0xFF,
            (address >> 16) & 0xFF,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (length >> 8) & 0xFF,
            length & 0xFF,
        ]
        resp = self._request(req, timeout_ms=int(WRITE_TIMEOUT * 1000))
        # Response contains max block size
        length_format = resp[1]
        num_bytes = (length_format >> 4) & 0x0F
        max_block = int.from_bytes(resp[2:2 + num_bytes], "big")
        log.info(f"Download accepted. Max block size: {max_block}")
        return max_block

    def transfer_data(self, block_sequence, data):
        """Transfer data block to ECU (service 0x36)."""
        req = bytes([SVC_TRANSFER_DATA, block_sequence & 0xFF]) + data
        resp = self._request(list(req), timeout_ms=int(WRITE_TIMEOUT * 1000))
        return resp

    def transfer_exit(self):
        """End data transfer (service 0x37)."""
        return self._request([SVC_TRANSFER_EXIT], timeout_ms=int(WRITE_TIMEOUT * 1000))

    def programming_mode(self):
        """Enter programming mode (service 0xA5) — GM-specific."""
        log.info("Entering programming mode")
        return self._request([SVC_PROGRAMMING_MODE, 0x01], timeout_ms=int(WRITE_TIMEOUT * 1000))

    # --- ECU Identification ---

    def read_vin(self):
        """Read Vehicle Identification Number."""
        try:
            data = self.read_data_by_id(DID_VIN)
            return data.decode("ascii", errors="replace").strip("\x00")
        except Exception as e:
            log.warning(f"Failed to read VIN: {e}")
            return "Unknown"

    def read_calibration_id(self):
        """Read calibration identification string."""
        try:
            data = self.read_data_by_id(DID_CALIBRATION_ID)
            return data.decode("ascii", errors="replace").strip("\x00")
        except Exception as e:
            log.warning(f"Failed to read cal ID: {e}")
            return "Unknown"

    def read_os_id(self):
        """Read operating system ID."""
        try:
            data = self.read_data_by_id(DID_OS_ID)
            return data.decode("ascii", errors="replace").strip("\x00")
        except Exception as e:
            log.warning(f"Failed to read OS ID: {e}")
            return "Unknown"

    def read_hardware_number(self):
        """Read ECU hardware part number."""
        try:
            data = self.read_data_by_id(DID_HARDWARE_NUMBER)
            return data.decode("ascii", errors="replace").strip("\x00")
        except Exception as e:
            log.warning(f"Failed to read HW number: {e}")
            return "Unknown"

    def read_battery_voltage(self):
        """Read battery voltage from ECU."""
        try:
            data = self.read_data_by_id(DID_BATTERY_VOLTAGE)
            if len(data) >= 2:
                raw = (data[0] << 8) | data[1]
                return raw * 0.001  # Convert to volts
            return 0.0
        except Exception:
            return 0.0

    def read_ecu_info(self):
        """Read all ECU identification data."""
        return {
            "vin": self.read_vin(),
            "calibration_id": self.read_calibration_id(),
            "os_id": self.read_os_id(),
            "hardware_number": self.read_hardware_number(),
            "battery_voltage": self.read_battery_voltage(),
        }

    # --- Tester Present ---

    def start_tester_present(self):
        """Start background thread sending TesterPresent keepalive."""
        if self._tester_running:
            return
        self._tester_running = True
        self._tester_thread = threading.Thread(target=self._tester_loop, daemon=True)
        self._tester_thread.start()
        log.info("TesterPresent keepalive started")

    def stop_tester_present(self):
        """Stop TesterPresent background thread."""
        self._tester_running = False
        if self._tester_thread:
            self._tester_thread.join(timeout=5)
        log.info("TesterPresent keepalive stopped")

    def _tester_loop(self):
        """Background loop sending TesterPresent at intervals."""
        while self._tester_running:
            try:
                self._j2534.send(bytes([SVC_TESTER_PRESENT, 0x00]))
            except Exception as e:
                log.warning(f"TesterPresent failed: {e}")
            time.sleep(TESTER_PRESENT_INTERVAL)
