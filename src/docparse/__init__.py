"""Local document parsing, chunking, and contextual text without service clients."""

from .config import ParserConfig, load_profile
from .sources import load_sources, build_document_manifest
from .hwp import parse_hwp
from .pdf import parse_pdf
from .chunk import chunk_documents
from .context import build_contextual_chunks


def parse_files(paths, config: ParserConfig = None, *, tables=None):
    config = config or ParserConfig()
    raw_docs = []
    for path in load_sources(paths, config):
        parser = parse_hwp if path.suffix.lower() == ".hwp" else parse_pdf
        raw_docs.extend(parser(path, config, tables=tables))
    return raw_docs


def run_all(paths, config: ParserConfig = None):
    config = config or ParserConfig()
    registry = {} if config.ir_enabled else None
    raw_docs = parse_files(paths, config, tables=registry)
    chunks = chunk_documents(raw_docs, config)
    contextual = build_contextual_chunks(chunks, config)
    result = {"raw_docs": raw_docs, "chunks": chunks, "contextual_chunks": contextual}
    if registry is not None:
        from .render import render_chunks
        chunks, contextual, full = render_chunks(raw_docs, chunks, contextual, registry, config)
        result.update(chunks=chunks, contextual_chunks=contextual,
                      tables=full, table_ir=registry)
    return result


__all__ = ["ParserConfig", "load_profile", "parse_files", "chunk_documents",
           "build_contextual_chunks", "run_all", "load_sources", "build_document_manifest"]
