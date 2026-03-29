"""J2534 PassThru DLL wrapper for Windows.

Discovers J2534 devices from the Windows registry and provides
a Python interface to the J2534 API via ctypes.
"""

import ctypes
from ctypes import c_ulong, c_char_p, byref, POINTER, Structure, c_void_p
import winreg
import logging

from ..config import (
    J2534_ISO15765, J2534_CAN, J2534_ISO15765_FRAME_PAD,
    J2534_FLOW_CONTROL, CAN_BAUD_RATE, CAN_REQUEST_ID, CAN_RESPONSE_ID,
    IOCTL_SET_CONFIG, IOCTL_CLEAR_TX_BUFFER, IOCTL_CLEAR_RX_BUFFER,
)
from ..exceptions import J2534Error, J2534DeviceNotFound

log = logging.getLogger(__name__)


# --- J2534 Structures ---

class PASSTHRU_MSG(Structure):
    _fields_ = [
        ("ProtocolID", c_ulong),
        ("RxStatus", c_ulong),
        ("TxFlags", c_ulong),
        ("Timestamp", c_ulong),
        ("DataSize", c_ulong),
        ("ExtraDataIndex", c_ulong),
        ("Data", ctypes.c_ubyte * 4128),
    ]


class SCONFIG(Structure):
    _fields_ = [
        ("Parameter", c_ulong),
        ("Value", c_ulong),
    ]


class SCONFIG_LIST(Structure):
    _fields_ = [
        ("NumOfParams", c_ulong),
        ("ConfigPtr", POINTER(SCONFIG)),
    ]


# J2534 error codes
J2534_ERRORS = {
    0x00: "STATUS_NOERROR",
    0x01: "ERR_NOT_SUPPORTED",
    0x02: "ERR_INVALID_CHANNEL_ID",
    0x03: "ERR_INVALID_PROTOCOL_ID",
    0x04: "ERR_NULL_PARAMETER",
    0x05: "ERR_INVALID_IOCTL_VALUE",
    0x06: "ERR_INVALID_FLAGS",
    0x07: "ERR_FAILED",
    0x08: "ERR_DEVICE_NOT_CONNECTED",
    0x09: "ERR_TIMEOUT",
    0x0A: "ERR_INVALID_MSG",
    0x0B: "ERR_INVALID_TIME_INTERVAL",
    0x0C: "ERR_EXCEEDED_LIMIT",
    0x0D: "ERR_INVALID_MSG_ID",
    0x0E: "ERR_DEVICE_IN_USE",
    0x0F: "ERR_INVALID_IOCTL_ID",
    0x10: "ERR_BUFFER_EMPTY",
    0x11: "ERR_BUFFER_FULL",
    0x12: "ERR_BUFFER_OVERFLOW",
    0x13: "ERR_PIN_INVALID",
    0x14: "ERR_CHANNEL_IN_USE",
    0x15: "ERR_MSG_PROTOCOL_ID",
    0x16: "ERR_INVALID_FILTER_ID",
    0x17: "ERR_NO_FLOW_CONTROL",
    0x18: "ERR_NOT_UNIQUE",
    0x19: "ERR_INVALID_BAUDRATE",
    0x1A: "ERR_INVALID_DEVICE_ID",
}


def discover_j2534_devices():
    """Find all installed J2534 devices from Windows registry.

    Returns list of dicts with 'name', 'dll_path', 'vendor'.
    """
    devices = []
    reg_path = r"SOFTWARE\PassThruSupport.04.04"

    for hive in [winreg.HKEY_LOCAL_MACHINE]:
        for access in [winreg.KEY_READ, winreg.KEY_READ | winreg.KEY_WOW64_32KEY]:
            try:
                key = winreg.OpenKey(hive, reg_path, 0, access)
            except OSError:
                continue

            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    try:
                        dll_path = winreg.QueryValueEx(subkey, "FunctionLibrary")[0]
                        vendor = ""
                        try:
                            vendor = winreg.QueryValueEx(subkey, "Vendor")[0]
                        except OSError:
                            pass
                        devices.append({
                            "name": subkey_name,
                            "dll_path": dll_path,
                            "vendor": vendor,
                        })
                    except OSError:
                        pass
                    finally:
                        winreg.CloseKey(subkey)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)

    return devices


class J2534:
    """J2534 PassThru interface wrapper."""

    def __init__(self):
        self._dll = None
        self._device_id = c_ulong(0)
        self._channel_id = c_ulong(0)
        self._filter_id = c_ulong(0)
        self._connected = False
        self._channel_open = False
        self.device_name = ""

    def _check(self, result, operation=""):
        """Check J2534 return code and raise on error."""
        if result != 0:
            err_name = J2534_ERRORS.get(result, f"UNKNOWN(0x{result:02X})")
            raise J2534Error(f"{operation}: {err_name}", result)

    def open(self, dll_path, device_name=""):
        """Open connection to J2534 device."""
        self.device_name = device_name
        log.info(f"Loading J2534 DLL: {dll_path}")

        try:
            self._dll = ctypes.WinDLL(dll_path)
        except OSError as e:
            raise J2534Error(f"Failed to load DLL: {dll_path}: {e}")

        ret = self._dll.PassThruOpen(c_void_p(0), byref(self._device_id))
        self._check(ret, "PassThruOpen")
        self._connected = True
        log.info(f"Opened J2534 device: {device_name} (id={self._device_id.value})")

    def close(self):
        """Close J2534 device."""
        if self._channel_open:
            self.disconnect()
        if self._connected and self._dll:
            try:
                self._dll.PassThruClose(self._device_id)
            except Exception:
                pass
            self._connected = False
            log.info("J2534 device closed")

    def connect(self, protocol=J2534_ISO15765, baud_rate=CAN_BAUD_RATE, flags=J2534_ISO15765_FRAME_PAD):
        """Open a communication channel."""
        if not self._connected:
            raise J2534Error("Device not open")

        ret = self._dll.PassThruConnect(
            self._device_id, c_ulong(protocol),
            c_ulong(flags), c_ulong(baud_rate),
            byref(self._channel_id)
        )
        self._check(ret, "PassThruConnect")
        self._channel_open = True
        self._protocol = protocol
        log.info(f"Channel opened: protocol={protocol}, baud={baud_rate}")

        # Set up flow control filter for ISO 15765
        self._setup_flow_control()

    def disconnect(self):
        """Close the communication channel."""
        if self._channel_open and self._dll:
            try:
                self._dll.PassThruDisconnect(self._channel_id)
            except Exception:
                pass
            self._channel_open = False
            log.info("Channel disconnected")

    def _setup_flow_control(self):
        """Set up ISO 15765 flow control filter for E38 ECU."""
        mask_msg = PASSTHRU_MSG()
        pattern_msg = PASSTHRU_MSG()
        flow_msg = PASSTHRU_MSG()

        for msg in [mask_msg, pattern_msg, flow_msg]:
            msg.ProtocolID = self._protocol
            msg.DataSize = 4

        # Mask: match all bits of the CAN ID
        mask_msg.Data[0] = 0xFF
        mask_msg.Data[1] = 0xFF
        mask_msg.Data[2] = 0xFF
        mask_msg.Data[3] = 0xFF

        # Pattern: match ECU response ID 0x07E8
        pattern_msg.Data[0] = (CAN_RESPONSE_ID >> 24) & 0xFF
        pattern_msg.Data[1] = (CAN_RESPONSE_ID >> 16) & 0xFF
        pattern_msg.Data[2] = (CAN_RESPONSE_ID >> 8) & 0xFF
        pattern_msg.Data[3] = CAN_RESPONSE_ID & 0xFF

        # Flow control: send from tester ID 0x07E0
        flow_msg.Data[0] = (CAN_REQUEST_ID >> 24) & 0xFF
        flow_msg.Data[1] = (CAN_REQUEST_ID >> 16) & 0xFF
        flow_msg.Data[2] = (CAN_REQUEST_ID >> 8) & 0xFF
        flow_msg.Data[3] = CAN_REQUEST_ID & 0xFF

        ret = self._dll.PassThruStartMsgFilter(
            self._channel_id, c_ulong(J2534_FLOW_CONTROL),
            byref(mask_msg), byref(pattern_msg), byref(flow_msg),
            byref(self._filter_id)
        )
        self._check(ret, "PassThruStartMsgFilter")
        log.info("Flow control filter set")

    def clear_buffers(self):
        """Clear TX and RX buffers."""
        self._dll.PassThruIoctl(self._channel_id, c_ulong(IOCTL_CLEAR_TX_BUFFER), c_void_p(0), c_void_p(0))
        self._dll.PassThruIoctl(self._channel_id, c_ulong(IOCTL_CLEAR_RX_BUFFER), c_void_p(0), c_void_p(0))

    def send(self, data, timeout_ms=1000):
        """Send an ISO 15765 message to the ECU.

        Args:
            data: bytes to send (without CAN ID prefix — the 4-byte ID is prepended automatically)
            timeout_ms: send timeout in milliseconds
        """
        msg = PASSTHRU_MSG()
        msg.ProtocolID = self._protocol
        msg.TxFlags = J2534_ISO15765_FRAME_PAD

        # 4-byte CAN ID + payload
        payload = CAN_REQUEST_ID.to_bytes(4, "big") + data
        msg.DataSize = len(payload)
        for i, b in enumerate(payload):
            msg.Data[i] = b

        num_msgs = c_ulong(1)
        ret = self._dll.PassThruWriteMsgs(
            self._channel_id, byref(msg), byref(num_msgs), c_ulong(timeout_ms)
        )
        self._check(ret, "PassThruWriteMsgs")
        log.debug(f"TX: {data.hex()}")

    def receive(self, timeout_ms=2000):
        """Receive an ISO 15765 message from the ECU.

        Returns:
            bytes: response payload (without CAN ID prefix)
        """
        msg = PASSTHRU_MSG()
        msg.ProtocolID = self._protocol
        num_msgs = c_ulong(1)

        ret = self._dll.PassThruReadMsgs(
            self._channel_id, byref(msg), byref(num_msgs), c_ulong(timeout_ms)
        )
        self._check(ret, "PassThruReadMsgs")

        if num_msgs.value == 0:
            return None

        # Skip 4-byte CAN ID prefix
        payload = bytes(msg.Data[4:msg.DataSize])
        log.debug(f"RX: {payload.hex()}")
        return payload

    def set_config(self, params):
        """Set channel configuration parameters.

        Args:
            params: dict of {parameter_id: value}
        """
        config_array = (SCONFIG * len(params))()
        for i, (param, value) in enumerate(params.items()):
            config_array[i].Parameter = param
            config_array[i].Value = value

        config_list = SCONFIG_LIST()
        config_list.NumOfParams = len(params)
        config_list.ConfigPtr = config_array

        ret = self._dll.PassThruIoctl(
            self._channel_id, c_ulong(IOCTL_SET_CONFIG),
            byref(config_list), c_void_p(0)
        )
        self._check(ret, "SetConfig")

    @property
    def is_connected(self):
        return self._connected

    @property
    def is_channel_open(self):
        return self._channel_open

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
