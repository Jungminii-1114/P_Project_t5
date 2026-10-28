"""Configurable copy of the frozen parsing algorithm."""

from .config import ParserConfig

import json
import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_hwp_hwpx import HwpHwpxLoader

# HWP 셀 텍스트에 섞여 들어오는 구조 마커 제거

def render_hwp_table(cells_json: str, config: ParserConfig = None) -> str:
    """HWP 표 cells(JSON)를 markdown 표로 복원한다 (병합 셀 전개)."""
    config = config or ParserConfig()
    marker = re.compile(config.hwp_marker_pattern)
    cells = json.loads(cells_json)
    nrows = max(c["row"] + max(c.get("rowspan", 1), 1) for c in cells)
    ncols = max(c["col"] + max(c.get("colspan", 1), 1) for c in cells)
    grid = [["" for _ in range(ncols)] for _ in range(nrows)]

    for c in cells:
        text = marker.sub(" ", c.get("text") or "")
        text = " ".join(text.split()).replace("|", "/")
        if text == config.image_marker:
            text = ""
        rowspan, colspan = max(c.get("rowspan", 1), 1), max(c.get("colspan", 1), 1)
        span = rowspan * colspan
        for r in range(c["row"], min(c["row"] + rowspan, nrows)):
            for col in range(c["col"], min(c["col"] + colspan, ncols)):
                # 넓게 병합된 셀은 좌상단에만 값을 두어 같은 문장이 반복되지 않게 한다
                if span == 1 or len(text) <= config.merged_repeat_max_chars or (r, col) == (c["row"], c["col"]):
                    grid[r][col] = text

    lines, prev = [], None
    for row in grid:
        if row == prev or not any(row):
            continue
        prev = row
        lines.append("| " + " | ".join(row) + " |")
    if not lines:
        return ""
    return lines[0] + "\n|" + "---|" * ncols + "\n" + "\n".join(lines[1:])


def parse_hwp(path: Path, config: ParserConfig = None):
    config = config or ParserConfig()
    elements = HwpHwpxLoader(str(path), mode=config.hwp_mode, distribution_backend=config.hwp_distribution_backend).load()
    docs = []
    for e in elements:
        kind = e.metadata.get("element_type")
        if kind == "body" and e.page_content.strip():
            docs.append(Document(page_content=e.page_content.strip(),
                                 metadata={"source": path.name, "page": 1, "kind": "text",
                                           "locator": {"type": "element_index", "value": int(e.metadata.get("element_index", 0))}}))
        elif kind == "table":
            table_md = render_hwp_table(e.metadata.get("cells", "[]"), config)
            if table_md:
                docs.append(Document(page_content=table_md,
                                     metadata={"source": path.name,
                                               "page": int(e.metadata.get("element_index", 0)) + 1,
                                               "kind": "table",
                                               "locator": {"type": "element_index", "value": int(e.metadata.get("element_index", 0))}}))
    return docs
