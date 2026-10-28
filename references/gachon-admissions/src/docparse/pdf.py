"""Configurable copy of the frozen parsing algorithm."""

from .config import ParserConfig

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


def parse_pdf(path: Path, config: ParserConfig = None, *, tables=None):
    config = config or ParserConfig()
    docs = []
    with pymupdf.open(str(path)) as doc:
        for i, page in enumerate(doc, start=1):
            text = normalize(page.get_text("text"), config)
            if text:
                docs.append(Document(page_content=text,
                                     metadata={"source": path.name, "page": i, "kind": "text", "locator": {"type": "page", "value": i}}))
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            found = page.find_tables() if tables is not None else None
            for ordinal, table in enumerate(page.extract_tables()):
                table_md = normalize(rows_to_markdown(table), config)
                if len(table_md) > config.pdf_table_min_chars:
                    metadata = {"source": path.name, "page": i, "kind": "table", "locator": {"type": "page", "value": i}}
                    if tables is not None:
                        from .extract_ir import pdf_table
                        ir = pdf_table(page, found[ordinal] if ordinal < len(found) else None,
                                       table, path.name, i, ordinal, config)
                        tables[ir.table_id] = ir
                        metadata["table_id"] = ir.table_id
                    docs.append(Document(page_content=table_md,
                                         metadata=metadata))
    return docs
