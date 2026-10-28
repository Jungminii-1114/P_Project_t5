# baseline-1 동결 레퍼런스 — v23(64ac263) build_notebook.py §1~§4에서 이식. 수정 금지. 개선은 새 버전에서.

from pathlib import Path

from .chunk import chunk_documents
from .context import build_contextual_chunks
from .hwp import parse_hwp, render_hwp_table
from .pdf import parse_pdf, rows_to_markdown
from .sources import build_document_manifest, load_sources, parse_required_files


def parse_documents(directory: Path):
    """필수 원문을 고정된 순서로 파싱해 Document 목록으로 반환한다."""
    return parse_required_files(directory, parse_hwp, parse_pdf)


def run_all(directory: Path):
    """원문 파싱부터 문맥 청크 구성까지 실행하고 각 단계 산출물을 반환한다."""
    raw_docs = parse_documents(directory)
    chunks = chunk_documents(raw_docs)
    contextual_chunks = build_contextual_chunks(chunks)
    return {
        "raw_docs": raw_docs,
        "chunks": chunks,
        "contextual_chunks": contextual_chunks,
    }


__all__ = [
    "load_sources",
    "parse_documents",
    "chunk_documents",
    "build_contextual_chunks",
    "run_all",
    "build_document_manifest",
    "render_hwp_table",
    "rows_to_markdown",
]
