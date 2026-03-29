"""E38 ECU security access algorithms.

Implements seed-key calculations for various E38 calibration types.
"""

import logging

log = logging.getLogger(__name__)

# Known algorithm variants for different E38 OS versions
ALGORITHMS = {
    "default": {
        "xor1": 0x9248,
        "rotate_bits": 5,
        "rotate_dir": "right",
        "xor2": 0x4F6E,
    },
    "ls3_e38": {
        "xor1": 0xA5C3,
        "rotate_bits": 7,
        "rotate_dir": "left",
        "xor2": 0x3D91,
    },
}


def compute_key_16bit(seed_bytes, xor1=0x9248, rotate_bits=5, rotate_dir="right", xor2=0x4F6E):
    """Compute 16-bit security key from seed."""
    seed = (seed_bytes[0] << 8) | seed_bytes[1]

    key = seed ^ xor1
    if rotate_dir == "right":
        key = ((key >> rotate_bits) | (key << (16 - rotate_bits))) & 0xFFFF
    else:
        key = ((key << rotate_bits) | (key >> (16 - rotate_bits))) & 0xFFFF
    key = key ^ xor2

    return key.to_bytes(2, "big")


def compute_key_32bit(seed_bytes, xor1=0x92484F6E, rotate_bits=13, rotate_dir="right", xor2=0x00000000):
    """Compute 32-bit security key from seed."""
    seed = int.from_bytes(seed_bytes, "big")

    key = seed ^ xor1
    if rotate_dir == "right":
        key = ((key >> rotate_bits) | (key << (32 - rotate_bits))) & 0xFFFFFFFF
    else:
        key = ((key << rotate_bits) | (key >> (32 - rotate_bits))) & 0xFFFFFFFF
    if xor2:
        key = key ^ xor2

    return key.to_bytes(4, "big")


def make_key_function(algorithm_name="default"):
    """Create a key computation function for the given algorithm variant.

    Returns a callable(seed_bytes) -> key_bytes.
    """
    params = ALGORITHMS.get(algorithm_name, ALGORITHMS["default"])

    def compute(seed_bytes):
        if len(seed_bytes) == 2:
            return compute_key_16bit(seed_bytes, **params)
        elif len(seed_bytes) == 4:
            return compute_key_32bit(seed_bytes)
        else:
            raise ValueError(f"Unexpected seed length: {len(seed_bytes)}")

    return compute


def brute_force_key(gmlan, max_attempts=65536, progress_cb=None):
    """Brute force 16-bit security key.

    This is a last resort when the algorithm is unknown.
    Tries all 65536 possible keys.

    Args:
        gmlan: GMLAN instance (already in extended session)
        max_attempts: max keys to try
        progress_cb: callable(attempt, total) for progress updates

    Returns:
        bytes: the correct key, or None if not found
    """
    from ..exceptions import NegativeResponse

    for attempt in range(max_attempts):
        if progress_cb and attempt % 100 == 0:
            progress_cb(attempt, max_attempts)

        try:
            # Request fresh seed
            resp = gmlan._request([0x27, 0x01], timeout_ms=2000)
            seed = resp[2:]

            if all(b == 0 for b in seed):
                log.info("ECU already unlocked")
                return b"\x00\x00"

            # Try this key value
            key = attempt.to_bytes(2, "big")
            gmlan._request([0x27, 0x02] + list(key), timeout_ms=2000)
            log.info(f"Key found: 0x{attempt:04X}")
            return key

        except NegativeResponse as e:
            if e.nrc == 0x35:  # Invalid key
                continue
            elif e.nrc == 0x36:  # Exceeded attempts
                log.warning("Exceeded attempts, waiting for timeout...")
                import time
                time.sleep(10)
                continue
            elif e.nrc == 0x37:  # Required time delay
                import time
                time.sleep(10)
                continue
            else:
                raise

    return None
