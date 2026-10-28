"""Portable table contract, including coordinates retained from source cells."""

from dataclasses import asdict, dataclass, field
import hashlib
import json


@dataclass
class Cell:
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    text: str = ""
    is_header: bool = False


@dataclass
class Table:
    table_id: str
    source: str
    locator: dict
    page: int
    n_rows: int
    n_cols: int
    cells: list[Cell]
    header_rows: int = 0
    stub_cols: int = 0
    origin: str = "pdf_fallback"
    confidence: str = "uncertain"
    diagnostics: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.origin not in {"hwp_cells", "pdf_cells", "pdf_fallback"}:
            raise ValueError("Unknown table origin")
        for cell in self.cells:
            if (min(cell.row, cell.col) < 0 or min(cell.rowspan, cell.colspan) < 1
                    or cell.row + cell.rowspan > self.n_rows
                    or cell.col + cell.colspan > self.n_cols):
                raise ValueError("Cell outside table bounds")

    def cell_at(self, row: int, col: int) -> Cell | None:
        return next((c for c in self.cells if c.row <= row < c.row+c.rowspan
                     and c.col <= col < c.col+c.colspan), None)

    def header_path(self, col: int) -> list[str]:
        return self._labels(self.cell_at(r, col) for r in range(self.header_rows))

    def row_label(self, row: int) -> list[str]:
        return self._labels(self.cell_at(row, c) for c in range(self.stub_cols))

    @staticmethod
    def _labels(cells):
        result = []
        for cell in cells:
            if cell and cell.text and (not result or result[-1] != cell.text):
                result.append(cell.text)
        return result

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, value: dict):
        value = dict(value)
        value["cells"] = [Cell(**cell) for cell in value["cells"]]
        return cls(**value)

    @classmethod
    def from_json(cls, value: str):
        return cls.from_dict(json.loads(value))


def table_id(source: str, locator: dict, ordinal: int) -> str:
    key = json.dumps([source, locator, ordinal], ensure_ascii=False, sort_keys=True)
    return "table_" + hashlib.sha256(key.encode()).hexdigest()[:24]
