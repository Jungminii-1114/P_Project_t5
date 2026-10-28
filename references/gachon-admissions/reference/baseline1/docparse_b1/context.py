# baseline-1 동결 레퍼런스 — v23(64ac263) build_notebook.py §4에서 이식. 수정 금지. 개선은 새 버전에서.

from langchain_core.documents import Document

from .constants import DOC_TITLES
from .table import parse_table, row_summary


def doc_title(source: str) -> str:
    return DOC_TITLES.get(source[:2], source)


def build_contextual_chunks(chunks):
    """색인용 텍스트 = 문맥 헤더 + (표 행 요약) + 원문. 원문은 metadata['raw']에 보관."""
    out, with_summary = [], 0
    for c in chunks:
        src, page, kind = c.metadata["source"], c.metadata["page"], c.metadata["kind"]
        title = doc_title(src)
        raw = c.page_content
        header = f"[문서] {title} | p.{page} | {'표' if kind == 'table' else '본문'}"
        summary = ""
        if kind == "table":
            caption, mode, cols, data = parse_table(raw)
            if caption:
                header += f" | 표제: {caption}"
            summary = row_summary(cols, data, mode)
            with_summary += bool(summary)
        body = header + (("\n[표 행 요약]\n" + summary) if summary else "") + "\n[원문]\n" + raw
        out.append(Document(page_content=body, metadata={**c.metadata, "raw": raw, "title": title}))
    n_table = sum(c.metadata["kind"] == "table" for c in chunks)
    print(f"색인용 청크 {len(out)}개 | 표 청크 {n_table}개 중 행 요약 {with_summary}개")
    return out
