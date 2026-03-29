"""1D and 2D table representations for calibration data."""

from .binary import read_value, write_value, TYPE_SIZES


class Table1D:
    """One-dimensional lookup table (vector)."""

    def __init__(self, definition, data=None):
        self.definition = definition
        self.size = definition.cols
        self.values = [0.0] * self.size
        self.axis = [0.0] * self.size

        if data is not None:
            self.load(data)

    def load(self, data):
        """Load table values from binary data."""
        d = self.definition
        cell_size = TYPE_SIZES[d.cell_dtype]

        for i in range(self.size):
            raw = read_value(data, d.offset + i * cell_size, d.cell_dtype)
            self.values[i] = raw * d.cell_scale + d.cell_bias

        if d.col_axis_offset:
            axis_size = TYPE_SIZES[d.axis_dtype]
            for i in range(self.size):
                raw = read_value(data, d.col_axis_offset + i * axis_size, d.axis_dtype)
                self.axis[i] = raw * d.axis_scale

    def save(self, data):
        """Write table values back to binary data."""
        d = self.definition
        cell_size = TYPE_SIZES[d.cell_dtype]

        for i in range(self.size):
            raw = (self.values[i] - d.cell_bias) / d.cell_scale
            raw = max(d.min_value / d.cell_scale, min(d.max_value / d.cell_scale, raw))
            write_value(data, d.offset + i * cell_size, d.cell_dtype, int(raw))

    def get(self, index):
        return self.values[index]

    def set(self, index, value):
        d = self.definition
        value = max(d.min_value, min(d.max_value, value))
        self.values[index] = value

    def scale_all(self, factor):
        """Multiply all values by a factor."""
        for i in range(self.size):
            self.values[i] *= factor


class Table2D:
    """Two-dimensional lookup table (map)."""

    def __init__(self, definition, data=None):
        self.definition = definition
        self.rows = definition.rows
        self.cols = definition.cols
        self.cells = [[0.0] * self.cols for _ in range(self.rows)]
        self.row_axis = [0.0] * self.rows
        self.col_axis = [0.0] * self.cols

        if data is not None:
            self.load(data)

    def load(self, data):
        """Load table from binary data."""
        d = self.definition
        cell_size = TYPE_SIZES[d.cell_dtype]

        # Load cell data (row-major order)
        for r in range(self.rows):
            for c in range(self.cols):
                offset = d.offset + (r * self.cols + c) * cell_size
                raw = read_value(data, offset, d.cell_dtype)
                self.cells[r][c] = raw * d.cell_scale + d.cell_bias

        # Load axis labels
        axis_size = TYPE_SIZES[d.axis_dtype]

        if d.row_axis_offset:
            for r in range(self.rows):
                raw = read_value(data, d.row_axis_offset + r * axis_size, d.axis_dtype)
                self.row_axis[r] = raw * d.axis_scale

        if d.col_axis_offset:
            for c in range(self.cols):
                raw = read_value(data, d.col_axis_offset + c * axis_size, d.axis_dtype)
                self.col_axis[c] = raw * d.axis_scale

    def save(self, data):
        """Write table back to binary data."""
        d = self.definition
        cell_size = TYPE_SIZES[d.cell_dtype]

        for r in range(self.rows):
            for c in range(self.cols):
                raw = (self.cells[r][c] - d.cell_bias) / d.cell_scale
                raw = max(d.min_value / d.cell_scale, min(d.max_value / d.cell_scale, raw))
                offset = d.offset + (r * self.cols + c) * cell_size
                write_value(data, offset, d.cell_dtype, int(raw))

    def get(self, row, col):
        return self.cells[row][col]

    def set(self, row, col, value):
        d = self.definition
        value = max(d.min_value, min(d.max_value, value))
        self.cells[row][col] = value

    def scale_all(self, factor):
        """Multiply all cells by a factor."""
        for r in range(self.rows):
            for c in range(self.cols):
                self.cells[r][c] *= factor

    def scale_row(self, row, factor):
        for c in range(self.cols):
            self.cells[row][c] *= factor

    def scale_col(self, col, factor):
        for r in range(self.rows):
            self.cells[r][col] *= factor

    def fill(self, value):
        """Set all cells to a single value."""
        for r in range(self.rows):
            for c in range(self.cols):
                self.cells[r][c] = value

    def copy_from(self, other):
        """Copy values from another Table2D of the same dimensions."""
        for r in range(min(self.rows, other.rows)):
            for c in range(min(self.cols, other.cols)):
                self.cells[r][c] = other.cells[r][c]

    def to_list(self):
        """Return cells as a flat list for display."""
        return [self.cells[r][c] for r in range(self.rows) for c in range(self.cols)]

    def min_cell(self):
        return min(v for row in self.cells for v in row)

    def max_cell(self):
        return max(v for row in self.cells for v in row)
