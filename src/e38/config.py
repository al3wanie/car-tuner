"""E38 ECU constants and configuration."""

# CAN Bus
CAN_BAUD_RATE = 500000
CAN_REQUEST_ID = 0x07E0
CAN_RESPONSE_ID = 0x07E8
CAN_FUNCTIONAL_ID = 0x07DF

# E38 Flash Memory Map
FLASH_BASE = 0x000000
FLASH_SIZE = 0x200000          # 2MB total
BOOT_BLOCK_START = 0x000000
BOOT_BLOCK_END = 0x00FFFF      # 64KB - NEVER modify
OS_START = 0x010000
OS_END = 0x1BFFFF              # ~1.75MB
CAL_START = 0x1C0000
CAL_END = 0x1FFFFF             # 256KB calibration
CAL_SIZE = CAL_END - CAL_START + 1  # 262144 bytes

# Read/Write block sizes
READ_BLOCK_SIZE = 4096         # 4KB per read request
WRITE_BLOCK_SIZE = 2048        # 2KB per transfer block

# UDS Service IDs
SVC_DIAGNOSTIC_SESSION = 0x10
SVC_ECU_RESET = 0x11
SVC_READ_DATA_BY_ID = 0x22
SVC_READ_MEMORY = 0x23
SVC_SECURITY_ACCESS = 0x27
SVC_COMMUNICATION_CONTROL = 0x28
SVC_REQUEST_DOWNLOAD = 0x34
SVC_REQUEST_UPLOAD = 0x35
SVC_TRANSFER_DATA = 0x36
SVC_TRANSFER_EXIT = 0x37
SVC_TESTER_PRESENT = 0x3E
SVC_PROGRAMMING_MODE = 0xA5
SVC_NEGATIVE_RESPONSE = 0x7F

# Diagnostic Session Types
SESSION_DEFAULT = 0x01
SESSION_PROGRAMMING = 0x02
SESSION_EXTENDED = 0x03

# Security Access
SECURITY_SEED_REQUEST = 0x01
SECURITY_KEY_SEND = 0x02

# Data Identifiers (DIDs) for ReadDataByIdentifier
DID_VIN = 0xF190
DID_CALIBRATION_ID = 0xF197
DID_OS_ID = 0xF195
DID_ECU_SERIAL = 0xF18C
DID_HARDWARE_NUMBER = 0xF191
DID_SOFTWARE_NUMBER = 0xF194
DID_BATTERY_VOLTAGE = 0x1141

# Timing (seconds)
TESTER_PRESENT_INTERVAL = 2.0
READ_TIMEOUT = 5.0
WRITE_TIMEOUT = 10.0
SECURITY_TIMEOUT = 5.0
ERASE_TIMEOUT = 30.0

# J2534 Protocol IDs
J2534_CAN = 5
J2534_ISO15765 = 6

# J2534 Connect Flags
J2534_CAN_29BIT_ID = 0x00000100
J2534_ISO15765_FRAME_PAD = 0x00000040

# J2534 Filter Types
J2534_PASS_FILTER = 0x01
J2534_BLOCK_FILTER = 0x02
J2534_FLOW_CONTROL = 0x03

# J2534 Ioctl IDs
IOCTL_SET_CONFIG = 0x02
IOCTL_CLEAR_TX_BUFFER = 0x07
IOCTL_CLEAR_RX_BUFFER = 0x08

# Backup directory
BACKUP_DIR = "backups/e38"

# NRC (Negative Response Codes)
NRC_NAMES = {
    0x10: "General Reject",
    0x11: "Service Not Supported",
    0x12: "Sub-Function Not Supported",
    0x13: "Incorrect Message Length",
    0x14: "Response Too Long",
    0x22: "Conditions Not Correct",
    0x24: "Request Sequence Error",
    0x25: "No Response From Sub-Net",
    0x31: "Request Out Of Range",
    0x33: "Security Access Denied",
    0x35: "Invalid Key",
    0x36: "Exceeded Number Of Attempts",
    0x37: "Required Time Delay Not Expired",
    0x70: "Upload/Download Not Accepted",
    0x71: "Transfer Data Suspended",
    0x72: "General Programming Failure",
    0x73: "Wrong Block Sequence Counter",
    0x78: "Request Correctly Received - Response Pending",
}
