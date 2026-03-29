"""Raw binary operations for E38 calibration files.

E38 uses a Motorola MPC5566 (PowerPC) — all multi-byte values are BIG ENDIAN.
"""

import struct
import hashlib


def load_bin(path):
    """Load a binary file."""
    with open(path, "rb") as f:
        return bytearray(f.read())


def save_bin(path, data):
    """Save binary data to file."""
    with open(path, "wb") as f:
        f.write(data)


def read_uint8(data, offset):
    return data[offset]


def write_uint8(data, offset, value):
    data[offset] = value & 0xFF


def read_uint16(data, offset):
    return struct.unpack_from(">H", data, offset)[0]


def write_uint16(data, offset, value):
    struct.pack_into(">H", data, offset, int(value) & 0xFFFF)


def read_int16(data, offset):
    return struct.unpack_from(">h", data, offset)[0]


def write_int16(data, offset, value):
    struct.pack_into(">h", data, offset, int(value))


def read_uint32(data, offset):
    return struct.unpack_from(">I", data, offset)[0]


def write_uint32(data, offset, value):
    struct.pack_into(">I", data, offset, int(value) & 0xFFFFFFFF)


def read_float32(data, offset):
    return struct.unpack_from(">f", data, offset)[0]


def write_float32(data, offset, value):
    struct.pack_into(">f", data, offset, float(value))


# Type dispatch
READERS = {
    "uint8": read_uint8,
    "uint16": read_uint16,
    "int16": read_int16,
    "uint32": read_uint32,
    "float32": read_float32,
}

WRITERS = {
    "uint8": write_uint8,
    "uint16": write_uint16,
    "int16": write_int16,
    "uint32": write_uint32,
    "float32": write_float32,
}

TYPE_SIZES = {
    "uint8": 1,
    "uint16": 2,
    "int16": 2,
    "uint32": 4,
    "float32": 4,
}


def read_value(data, offset, dtype):
    """Read a value of the given type from binary data."""
    return READERS[dtype](data, offset)


def write_value(data, offset, dtype, value):
    """Write a value of the given type to binary data."""
    WRITERS[dtype](data, offset, value)


def compute_checksum(data, start=0, end=None):
    """Compute additive checksum over a range.

    E38 uses a 32-bit additive checksum over the calibration region.
    """
    if end is None:
        end = len(data)

    total = 0
    for i in range(start, end, 4):
        if i + 4 <= end:
            total += read_uint32(data, i)
        else:
            # Handle partial last word
            remaining = end - i
            val = 0
            for j in range(remaining):
                val = (val << 8) | data[i + j]
            val <<= (4 - remaining) * 8
            total += val
        total &= 0xFFFFFFFF

    return total


def sha256(data):
    """Compute SHA-256 hash of binary data."""
    return hashlib.sha256(bytes(data)).hexdigest()


def diff_binary(data1, data2):
    """Compare two binary buffers and return differences.

    Returns:
        list of (offset, old_byte, new_byte) tuples
    """
    diffs = []
    for i in range(min(len(data1), len(data2))):
        if data1[i] != data2[i]:
            diffs.append((i, data1[i], data2[i]))
    return diffs
