"""Parameter definition schema for E38 calibration."""

from dataclasses import dataclass, field


@dataclass
class ParamDef:
    """Definition of a single tunable parameter."""
    name: str
    category: str
    offset: int                     # Byte offset within calibration section
    dtype: str = "uint16"           # uint8, uint16, int16, uint32, float32
    scale: float = 1.0              # raw_value * scale = engineering value
    bias: float = 0.0               # engineering = raw * scale + bias
    units: str = ""
    min_value: float = 0
    max_value: float = 65535
    description: str = ""
    dangerous: bool = False         # Extra warning before modification


@dataclass
class TableDef:
    """Definition of a 2D lookup table."""
    name: str
    category: str
    offset: int                     # Start offset of table data
    rows: int = 16                  # Number of rows
    cols: int = 16                  # Number of columns
    cell_dtype: str = "uint16"      # Data type of each cell
    cell_scale: float = 1.0
    cell_bias: float = 0.0
    cell_units: str = ""
    row_axis_offset: int = 0        # Offset of row axis labels
    col_axis_offset: int = 0        # Offset of column axis labels
    axis_dtype: str = "uint16"
    axis_scale: float = 1.0
    row_units: str = "RPM"
    col_units: str = "kPa"
    description: str = ""
    min_value: float = 0
    max_value: float = 65535


@dataclass
class BitParamDef:
    """Definition of a single-bit parameter (enable/disable flags)."""
    name: str
    category: str
    offset: int                     # Byte offset
    bit: int                        # Bit position (0-7)
    inverted: bool = False          # True if 0=enabled, 1=disabled
    description: str = ""


@dataclass
class DTCDef:
    """Definition of a DTC enable/disable flag."""
    code: str                       # e.g. "P0101"
    name: str                       # e.g. "MAF Sensor Range/Performance"
    offset: int                     # Byte offset in calibration
    bit: int                        # Bit position (0-7)
    inverted: bool = False
    category: str = "Powertrain"
