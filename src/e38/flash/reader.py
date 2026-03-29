"""E38 ECU flash memory reader."""

import time
import logging

from ..config import (
    FLASH_BASE, FLASH_SIZE, CAL_START, CAL_END, CAL_SIZE,
    READ_BLOCK_SIZE, SESSION_EXTENDED,
)
from ..comm.gmlan import GMLAN
from ..exceptions import FlashError

log = logging.getLogger(__name__)


def read_calibration(gmlan: GMLAN, progress_cb=None):
    """Read the 256KB calibration section from E38 ECU.

    Args:
        gmlan: connected GMLAN instance
        progress_cb: callable(bytes_read, total_bytes) for progress

    Returns:
        bytes: 256KB calibration data
    """
    return _read_range(gmlan, CAL_START, CAL_SIZE, progress_cb)


def read_full_flash(gmlan: GMLAN, progress_cb=None):
    """Read the entire 2MB flash from E38 ECU.

    Args:
        gmlan: connected GMLAN instance
        progress_cb: callable(bytes_read, total_bytes) for progress

    Returns:
        bytes: 2MB flash data
    """
    return _read_range(gmlan, FLASH_BASE, FLASH_SIZE, progress_cb)


def _read_range(gmlan: GMLAN, start_address, total_length, progress_cb=None):
    """Read a range of flash memory.

    Sequence:
    1. Enter extended diagnostic session
    2. Disable normal communication
    3. Security access
    4. Read memory in blocks
    5. Restore communication
    """
    data = bytearray()

    try:
        # Step 1: Extended session
        gmlan.start_diagnostic_session(SESSION_EXTENDED)
        gmlan.start_tester_present()

        # Step 2: Disable normal comm
        gmlan.disable_normal_communication()

        # Step 3: Security access
        gmlan.security_access()

        # Step 4: Read in blocks
        address = start_address
        remaining = total_length
        block_num = 0

        log.info(f"Reading {total_length} bytes from 0x{start_address:06X}...")
        start_time = time.time()

        while remaining > 0:
            block_size = min(READ_BLOCK_SIZE, remaining)

            try:
                block = gmlan.read_memory_by_address(address, block_size)
                data.extend(block)
            except Exception as e:
                raise FlashError(
                    f"Read failed at 0x{address:06X} (block {block_num}): {e}"
                )

            remaining -= block_size
            address += block_size
            block_num += 1

            if progress_cb:
                progress_cb(len(data), total_length)

        elapsed = time.time() - start_time
        log.info(f"Read complete: {len(data)} bytes in {elapsed:.1f}s")

    finally:
        gmlan.stop_tester_present()
        try:
            gmlan.enable_normal_communication()
        except Exception:
            pass

    if len(data) != total_length:
        raise FlashError(f"Read size mismatch: got {len(data)}, expected {total_length}")

    return bytes(data)
