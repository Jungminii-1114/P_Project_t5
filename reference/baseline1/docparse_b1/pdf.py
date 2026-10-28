# baseline-1 동결 레퍼런스 — v23(64ac263) build_notebook.py §2에서 이식. 수정 금지. 개선은 새 버전에서.

from pathlib import Path

import pdfplumber
try:
    import pymupdf
except ImportError:  # 구버전 호환
    import fitz as pymupdf

from langchain_core.documents import Document

from .text import normalize


def rows_to_markdown(rows) -> str:
    """pdfplumber 표(2차원 리스트)를 markdown 표로 변환한다 (빈 행/열 제거)."""
    if not rows:
        return ""
    ncols = max(len(r) for r in rows)
    rows = [[(c or "").replace("\n", " ").strip() for c in r] + [""] * (ncols - len(r)) for r in rows]
    keep = [j for j in range(ncols) if any(r[j] for r in rows)]
    rows = [[r[j] for j in keep] for r in rows]
    rows = [r for r in rows if any(r)]
    if len(rows) < 2:
        return ""
    body = "\n".join("| " + " | ".join(c.replace("|", "/") for c in r) + " |" for r in rows[1:])
    return "| " + " | ".join(rows[0]) + " |\n|" + "---|" * len(keep) + "\n" + body


def parse_pdf(path: Path):
    docs = []
    with pymupdf.open(str(path)) as doc:
        for i, page in enumerate(doc, start=1):
            text = normalize(page.get_text("text"))
            if text:
                docs.append(Document(page_content=text,
                                     metadata={"source": path.name, "page": i, "kind": "text"}))
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables():
                table_md = normalize(rows_to_markdown(table))
                if len(table_md) > 60:
                    docs.append(Document(page_content=table_md,
                                         metadata={"source": path.name, "page": i, "kind": "table"}))
    return docs
