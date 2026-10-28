"""Conservative, document-independent header and stub inference."""

from .config import ParserConfig
from .table import is_value


def infer_structure(table, config: ParserConfig = None):
    config = config or ParserConfig()
    # Horizontally merged upper bands remain headers even if their text is numeric.
    first_value_row = None
    for row in range(table.n_rows):
        starts = [c for c in table.cells if c.row == row and c.text]
        values = [c for c in starts if is_value(c.text, config)]
        first_value_col = min((c.col for c in values), default=table.n_cols)
        # Merged row labels to the left of values are data, not header bands.
        merged_band = any(c.col >= first_value_col and c.colspan > 1
                          and not is_value(c.text, config) for c in starts)
        if values and not (merged_band and row < config.ir_max_header_rows):
            first_value_row = row
            break
    table.header_rows = first_value_row or 0
    if table.header_rows > config.ir_max_header_rows:
        table.header_rows = 0
    first_values = []
    for row in range(table.header_rows, table.n_rows):
        cols = [c.col for c in table.cells if c.row <= row < c.row+c.rowspan
                and is_value(c.text, config)]
        if cols:
            first_values.append(min(cols))
    # A column is a stub only if it precedes all observed value cells.
    table.stub_cols = min(first_values, default=0)
    table.confidence = "confident" if (0 < table.header_rows < table.n_rows
        and 0 < table.stub_cols < table.n_cols) else "uncertain"
    for cell in table.cells:
        cell.is_header = cell.row < table.header_rows or cell.col < table.stub_cols
    table.diagnostics["structure_reason"] = (
        "value_boundary" if table.confidence == "confident" else "missing_or_ambiguous_boundary")
    return table
