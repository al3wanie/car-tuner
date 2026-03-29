"""Backup management for E38 calibration files."""

import os
import json
import hashlib
import time
import logging

from ..config import BACKUP_DIR

log = logging.getLogger(__name__)


def get_backup_dir(base_path="."):
    """Get the backup directory path, creating it if needed."""
    path = os.path.join(base_path, BACKUP_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def create_backup(binary_data, ecu_info=None, base_path="."):
    """Save a backup of calibration/flash data.

    Args:
        binary_data: bytes of the calibration or full flash
        ecu_info: dict with VIN, calibration_id, os_id, etc.
        base_path: project root directory

    Returns:
        tuple: (bin_path, meta_path)
    """
    backup_dir = get_backup_dir(base_path)
    ecu_info = ecu_info or {}

    vin = ecu_info.get("vin", "UNKNOWN").replace(" ", "_")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    sha256 = hashlib.sha256(binary_data).hexdigest()

    filename = f"E38_{vin}_{timestamp}"
    bin_path = os.path.join(backup_dir, f"{filename}.bin")
    meta_path = os.path.join(backup_dir, f"{filename}.json")

    # Save binary
    with open(bin_path, "wb") as f:
        f.write(binary_data)

    # Save metadata
    metadata = {
        "filename": f"{filename}.bin",
        "timestamp": timestamp,
        "size": len(binary_data),
        "sha256": sha256,
        "vin": ecu_info.get("vin", "Unknown"),
        "calibration_id": ecu_info.get("calibration_id", "Unknown"),
        "os_id": ecu_info.get("os_id", "Unknown"),
        "hardware_number": ecu_info.get("hardware_number", "Unknown"),
        "type": "calibration" if len(binary_data) == 262144 else "full_flash",
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    log.info(f"Backup saved: {bin_path}")
    return bin_path, meta_path


def list_backups(base_path="."):
    """List all backups with metadata.

    Returns:
        list of dicts with backup metadata
    """
    backup_dir = get_backup_dir(base_path)
    backups = []

    for fname in sorted(os.listdir(backup_dir), reverse=True):
        if fname.endswith(".json"):
            meta_path = os.path.join(backup_dir, fname)
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                bin_path = os.path.join(backup_dir, meta.get("filename", fname.replace(".json", ".bin")))
                meta["bin_path"] = bin_path
                meta["meta_path"] = meta_path
                meta["exists"] = os.path.exists(bin_path)
                backups.append(meta)
            except Exception as e:
                log.warning(f"Failed to read backup metadata {fname}: {e}")

    return backups


def load_backup(bin_path):
    """Load a backup binary file.

    Returns:
        bytes: the binary data
    """
    with open(bin_path, "rb") as f:
        return f.read()


def verify_backup(bin_path, meta_path=None):
    """Verify backup integrity by comparing SHA-256 hash.

    Returns:
        tuple: (is_valid, message)
    """
    if not os.path.exists(bin_path):
        return False, f"File not found: {bin_path}"

    with open(bin_path, "rb") as f:
        data = f.read()

    actual_hash = hashlib.sha256(data).hexdigest()

    if meta_path is None:
        meta_path = bin_path.replace(".bin", ".json")

    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        expected_hash = meta.get("sha256", "")
        if actual_hash == expected_hash:
            return True, "Backup integrity verified"
        else:
            return False, f"Hash mismatch! Expected {expected_hash[:16]}..., got {actual_hash[:16]}..."

    return True, f"No metadata found. SHA-256: {actual_hash[:16]}..."


def compare_backups(path1, path2):
    """Compare two backup files byte by byte.

    Returns:
        list of dicts: [{"offset": int, "file1": int, "file2": int}, ...]
    """
    with open(path1, "rb") as f:
        data1 = f.read()
    with open(path2, "rb") as f:
        data2 = f.read()

    diffs = []
    max_len = max(len(data1), len(data2))

    for i in range(max_len):
        b1 = data1[i] if i < len(data1) else None
        b2 = data2[i] if i < len(data2) else None
        if b1 != b2:
            diffs.append({
                "offset": i,
                "file1": b1,
                "file2": b2,
            })

    return diffs
