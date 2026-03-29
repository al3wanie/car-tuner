"""High-level parameter access API for E38 calibration."""

import logging

from .binary import read_value, write_value, TYPE_SIZES, load_bin, save_bin, compute_checksum, sha256, diff_binary
from .tables import Table1D, Table2D
from .definition import ParamDef, TableDef, BitParamDef, DTCDef
from ..exceptions import ParameterError, ParameterOutOfRange

log = logging.getLogger(__name__)


class CalibrationEditor:
    """High-level editor for E38 calibration binary data."""

    def __init__(self, data, param_defs, table_defs, bit_defs, dtc_defs):
        """
        Args:
            data: bytearray of calibration data (256KB)
            param_defs: dict of {name: ParamDef}
            table_defs: dict of {name: TableDef}
            bit_defs: dict of {name: BitParamDef}
            dtc_defs: dict of {code: DTCDef}
        """
        self.data = bytearray(data)
        self.original = bytes(data)  # Immutable copy for diff
        self.params = param_defs
        self.tables = table_defs
        self.bits = bit_defs
        self.dtcs = dtc_defs
        self._changes = []

    @classmethod
    def from_file(cls, path, param_defs, table_defs, bit_defs, dtc_defs):
        """Load calibration from a .bin file."""
        data = load_bin(path)
        return cls(data, param_defs, table_defs, bit_defs, dtc_defs)

    def save(self, path):
        """Save modified calibration to file."""
        save_bin(path, self.data)
        log.info(f"Calibration saved to {path}")

    # --- Scalar Parameters ---

    def get_param(self, name):
        """Get a parameter's engineering value."""
        if name not in self.params:
            raise ParameterError(f"Unknown parameter: {name}")
        p = self.params[name]
        raw = read_value(self.data, p.offset, p.dtype)
        return raw * p.scale + p.bias

    def set_param(self, name, value):
        """Set a parameter to an engineering value."""
        if name not in self.params:
            raise ParameterError(f"Unknown parameter: {name}")
        p = self.params[name]

        if value < p.min_value or value > p.max_value:
            raise ParameterOutOfRange(name, value, p.min_value, p.max_value)

        raw = int((value - p.bias) / p.scale)
        old_raw = read_value(self.data, p.offset, p.dtype)
        write_value(self.data, p.offset, p.dtype, raw)

        self._changes.append({
            "type": "param",
            "name": name,
            "old": old_raw * p.scale + p.bias,
            "new": value,
        })
        log.info(f"Set {name} = {value} {p.units}")

    def get_param_info(self, name):
        """Get parameter definition and current value."""
        p = self.params[name]
        return {
            "name": p.name,
            "value": self.get_param(name),
            "units": p.units,
            "min": p.min_value,
            "max": p.max_value,
            "category": p.category,
            "description": p.description,
            "dangerous": p.dangerous,
        }

    # --- Bit Parameters ---

    def get_bit(self, name):
        """Get a bit parameter (returns True/False for enabled/disabled)."""
        if name not in self.bits:
            raise ParameterError(f"Unknown bit parameter: {name}")
        b = self.bits[name]
        byte_val = self.data[b.offset]
        bit_set = bool(byte_val & (1 << b.bit))
        return not bit_set if b.inverted else bit_set

    def set_bit(self, name, enabled):
        """Set a bit parameter on/off."""
        if name not in self.bits:
            raise ParameterError(f"Unknown bit parameter: {name}")
        b = self.bits[name]

        if b.inverted:
            enabled = not enabled

        old_val = self.data[b.offset]
        if enabled:
            self.data[b.offset] = old_val | (1 << b.bit)
        else:
            self.data[b.offset] = old_val & ~(1 << b.bit)

        self._changes.append({
            "type": "bit",
            "name": name,
            "old": not (not (old_val & (1 << b.bit)) if b.inverted else bool(old_val & (1 << b.bit))),
            "new": not enabled if b.inverted else enabled,
        })

    # --- DTC Management ---

    def get_dtc_enabled(self, code):
        """Check if a DTC is enabled."""
        if code not in self.dtcs:
            raise ParameterError(f"Unknown DTC: {code}")
        d = self.dtcs[code]
        byte_val = self.data[d.offset]
        bit_set = bool(byte_val & (1 << d.bit))
        return not bit_set if d.inverted else bit_set

    def set_dtc_enabled(self, code, enabled):
        """Enable or disable a DTC."""
        if code not in self.dtcs:
            raise ParameterError(f"Unknown DTC: {code}")
        d = self.dtcs[code]

        if d.inverted:
            enabled = not enabled

        if enabled:
            self.data[d.offset] = self.data[d.offset] | (1 << d.bit)
        else:
            self.data[d.offset] = self.data[d.offset] & ~(1 << d.bit)

        self._changes.append({
            "type": "dtc",
            "code": code,
            "name": d.name,
            "enabled": not enabled if d.inverted else enabled,
        })

    def disable_all_dtcs(self):
        """Disable all known DTCs."""
        for code in self.dtcs:
            self.set_dtc_enabled(code, False)

    def enable_all_dtcs(self):
        """Enable all known DTCs."""
        for code in self.dtcs:
            self.set_dtc_enabled(code, True)

    # --- Tables ---

    def get_table(self, name):
        """Load and return a Table2D object."""
        if name not in self.tables:
            raise ParameterError(f"Unknown table: {name}")
        td = self.tables[name]
        if td.rows == 1:
            return Table1D(td, self.data)
        return Table2D(td, self.data)

    def set_table(self, name, table):
        """Write a modified table back to binary data."""
        if name not in self.tables:
            raise ParameterError(f"Unknown table: {name}")
        table.save(self.data)
        self._changes.append({
            "type": "table",
            "name": name,
        })

    # --- Categories ---

    def get_categories(self):
        """Get all parameter categories."""
        cats = set()
        for p in self.params.values():
            cats.add(p.category)
        for t in self.tables.values():
            cats.add(t.category)
        for b in self.bits.values():
            cats.add(b.category)
        return sorted(cats)

    def get_params_by_category(self, category):
        """Get all scalar parameters in a category."""
        return {n: p for n, p in self.params.items() if p.category == category}

    def get_tables_by_category(self, category):
        """Get all table parameters in a category."""
        return {n: t for n, t in self.tables.items() if t.category == category}

    def get_bits_by_category(self, category):
        """Get all bit parameters in a category."""
        return {n: b for n, b in self.bits.items() if b.category == category}

    # --- Changes & Diff ---

    def get_changes(self):
        """Return list of all modifications made."""
        return self._changes

    def get_byte_diff(self):
        """Compare current data against original."""
        return diff_binary(self.original, self.data)

    def is_modified(self):
        """Check if any changes have been made."""
        return self.data != self.original

    def revert(self):
        """Revert all changes."""
        self.data = bytearray(self.original)
        self._changes.clear()

    def get_hash(self):
        """Get SHA-256 hash of current calibration data."""
        return sha256(self.data)

    def export(self):
        """Export the modified calibration as bytes."""
        return bytes(self.data)
