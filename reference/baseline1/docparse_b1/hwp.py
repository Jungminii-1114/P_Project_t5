# baseline-1 동결 레퍼런스 — v23(64ac263) build_notebook.py §2에서 이식. 수정 금지. 개선은 새 버전에서.

import json
import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_hwp_hwpx import HwpHwpxLoader

# HWP 셀 텍스트에 섞여 들어오는 구조 마커 제거
_MARKER = re.compile(
    r"\[(?:rowspan=\d+,\s*colspan=\d+|colspan=\d+,\s*rowspan=\d+|merged:[^\]]+)\]"
)


def render_hwp_table(cells_json: str) -> str:
    """HWP 표 cells(JSON)를 markdown 표로 복원한다 (병합 셀 전개)."""
    cells = json.loads(cells_json)
    nrows = max(c["row"] + max(c.get("rowspan", 1), 1) for c in cells)
    ncols = max(c["col"] + max(c.get("colspan", 1), 1) for c in cells)
    grid = [["" for _ in range(ncols)] for _ in range(nrows)]

    for c in cells:
        text = _MARKER.sub(" ", c.get("text") or "")
        text = " ".join(text.split()).replace("|", "/")
        if text == "[IMAGE]":
            text = ""
        rowspan, colspan = max(c.get("rowspan", 1), 1), max(c.get("colspan", 1), 1)
        span = rowspan * colspan
        for r in range(c["row"], min(c["row"] + rowspan, nrows)):
            for col in range(c["col"], min(c["col"] + colspan, ncols)):
                # 넓게 병합된 셀은 좌상단에만 값을 두어 같은 문장이 반복되지 않게 한다
                if span == 1 or len(text) <= 40 or (r, col) == (c["row"], c["col"]):
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


def parse_hwp(path: Path):
    elements = HwpHwpxLoader(str(path), mode="elements", distribution_backend="pyhwp").load()
    docs = []
    for e in elements:
        kind = e.metadata.get("element_type")
        if kind == "body" and e.page_content.strip():
            docs.append(Document(page_content=e.page_content.strip(),
                                 metadata={"source": path.name, "page": 1, "kind": "text"}))
        elif kind == "table":
            table_md = render_hwp_table(e.metadata.get("cells", "[]"))
            if table_md:
                docs.append(Document(page_content=table_md,
                                     metadata={"source": path.name,
                                               "page": int(e.metadata.get("element_index", 0)) + 1,
                                               "kind": "table"}))
    return docs
