"""E38 ECU flash memory writer."""

import time
import logging

from ..config import (
    CAL_START, CAL_SIZE, WRITE_BLOCK_SIZE,
    SESSION_PROGRAMMING,
)
from ..comm.gmlan import GMLAN
from ..exceptions import FlashError, FlashVerifyError, LowVoltageError
from .reader import read_calibration

log = logging.getLogger(__name__)

MIN_BATTERY_VOLTAGE = 12.0


def write_calibration(gmlan: GMLAN, cal_data, verify=True, progress_cb=None):
    """Write calibration data to E38 ECU.

    Args:
        gmlan: connected GMLAN instance
        cal_data: bytes, exactly 256KB (262144 bytes) of calibration data
        verify: if True, read back and compare after write
        progress_cb: callable(bytes_written, total_bytes, phase) for progress
            phase is "check", "erase", "write", "verify"

    Raises:
        FlashError: on any write failure
        FlashVerifyError: if verification fails
        LowVoltageError: if battery voltage is too low
    """
    if len(cal_data) != CAL_SIZE:
        raise FlashError(f"Calibration data must be {CAL_SIZE} bytes, got {len(cal_data)}")

    try:
        # Step 1: Check battery voltage
        if progress_cb:
            progress_cb(0, CAL_SIZE, "check")

        voltage = gmlan.read_battery_voltage()
        if voltage > 0 and voltage < MIN_BATTERY_VOLTAGE:
            raise LowVoltageError(voltage)
        log.info(f"Battery voltage: {voltage:.1f}V")

        # Step 2: Enter programming session
        gmlan.start_diagnostic_session(SESSION_PROGRAMMING)
        gmlan.start_tester_present()

        # Step 3: Disable normal communication
        gmlan.disable_normal_communication()

        # Step 4: Security access
        gmlan.security_access()

        # Step 5: Enter programming mode
        gmlan.programming_mode()

        # Step 6: Request download
        if progress_cb:
            progress_cb(0, CAL_SIZE, "erase")

        max_block = gmlan.request_download(CAL_START, CAL_SIZE)
        block_size = min(WRITE_BLOCK_SIZE, max_block - 2)  # -2 for service byte + sequence
        log.info(f"Using block size: {block_size}")

        # Step 7: Transfer data
        if progress_cb:
            progress_cb(0, CAL_SIZE, "write")

        offset = 0
        block_seq = 0
        start_time = time.time()

        while offset < CAL_SIZE:
            chunk_size = min(block_size, CAL_SIZE - offset)
            chunk = cal_data[offset:offset + chunk_size]

            block_seq = (block_seq + 1) & 0xFF  # Wrap at 255
            try:
                gmlan.transfer_data(block_seq, chunk)
            except Exception as e:
                raise FlashError(
                    f"Transfer failed at offset 0x{offset:06X} "
                    f"(block {block_seq}): {e}"
                )

            offset += chunk_size
            if progress_cb:
                progress_cb(offset, CAL_SIZE, "write")

        elapsed = time.time() - start_time
        log.info(f"Write complete: {CAL_SIZE} bytes in {elapsed:.1f}s")

        # Step 8: End transfer
        gmlan.transfer_exit()

        # Step 9: Verify (read back and compare)
        if verify:
            if progress_cb:
                progress_cb(0, CAL_SIZE, "verify")

            log.info("Verifying flash...")

            # Need to go back to extended session for reading
            gmlan.start_diagnostic_session()
            gmlan.disable_normal_communication()
            gmlan.security_access()

            readback = read_calibration(gmlan, progress_cb=lambda done, total: (
                progress_cb(done, total, "verify") if progress_cb else None
            ))

            for i in range(CAL_SIZE):
                if readback[i] != cal_data[i]:
                    raise FlashVerifyError(CAL_START + i, cal_data[i], readback[i])

            log.info("Verification PASSED")

    finally:
        gmlan.stop_tester_present()
        try:
            gmlan.enable_normal_communication()
        except Exception:
            pass

    return True
