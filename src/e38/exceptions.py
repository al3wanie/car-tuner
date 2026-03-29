"""Custom exceptions for E38 tuner."""

from .config import NRC_NAMES


class E38Error(Exception):
    """Base exception for all E38 tuner errors."""


class J2534Error(E38Error):
    """J2534 adapter communication error."""
    def __init__(self, message, error_code=None):
        self.error_code = error_code
        super().__init__(f"J2534 Error: {message}" + (f" (code {error_code})" if error_code else ""))


class J2534DeviceNotFound(J2534Error):
    """No J2534 device found in registry."""
    def __init__(self):
        super().__init__("No J2534 device found. Install a J2534 driver.")


class CANError(E38Error):
    """CAN bus communication error."""


class CANTimeout(CANError):
    """No response from ECU within timeout."""
    def __init__(self, timeout):
        super().__init__(f"No response from ECU within {timeout}s")


class GMLANError(E38Error):
    """GMLAN protocol error."""


class NegativeResponse(GMLANError):
    """ECU returned a negative response."""
    def __init__(self, service_id, nrc):
        self.service_id = service_id
        self.nrc = nrc
        name = NRC_NAMES.get(nrc, "Unknown")
        super().__init__(f"ECU rejected service 0x{service_id:02X}: 0x{nrc:02X} ({name})")


class SecurityAccessDenied(GMLANError):
    """Failed to unlock ECU security."""


class FlashError(E38Error):
    """Flash read/write error."""


class FlashVerifyError(FlashError):
    """Flash verification failed after write."""
    def __init__(self, offset, expected, actual):
        self.offset = offset
        super().__init__(
            f"Verify failed at 0x{offset:06X}: "
            f"expected 0x{expected:02X}, got 0x{actual:02X}"
        )


class ChecksumError(E38Error):
    """Calibration checksum mismatch."""


class ParameterError(E38Error):
    """Invalid parameter value or name."""


class ParameterOutOfRange(ParameterError):
    """Parameter value outside safe limits."""
    def __init__(self, name, value, min_val, max_val):
        super().__init__(
            f"{name}: {value} out of range [{min_val}, {max_val}]"
        )


class LowVoltageError(FlashError):
    """Battery voltage too low for safe flashing."""
    def __init__(self, voltage):
        self.voltage = voltage
        super().__init__(f"Battery voltage {voltage:.1f}V too low. Need >= 12.0V for safe flash.")
