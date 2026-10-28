"""Configurable copy of the frozen parsing algorithm."""

from langchain_core.documents import Document

from .config import ParserConfig
from pathlib import Path
import re
from .table import parse_table, row_summary


def doc_title(source: str, config: ParserConfig = None) -> str:
    config = config or ParserConfig()
    key = source[:config.title_prefix_length] if config.title_prefix_length is not None else source
    if key in config.title_map:
        return config.title_map[key]
    if config.title_fallback_source:
        return source
    return re.sub(config.title_cleanup_pattern, "", Path(source).stem).replace("_", " ").strip()


def build_contextual_chunks(chunks, config: ParserConfig = None):
    """색인용 텍스트 = 문맥 헤더 + (표 행 요약) + 원문. 원문은 metadata['raw']에 보관."""
    config = config or ParserConfig()
    out, with_summary = [], 0
    for c in chunks:
        src, page, kind = c.metadata["source"], c.metadata["page"], c.metadata["kind"]
        title = doc_title(src, config)
        raw = c.page_content
        header = config.context_header_template.format(title=title, page=page,
            kind_label=config.kind_labels.get(kind, kind), source=src, kind=kind)
        summary = ""
        if kind == "table":
            caption, mode, cols, data = parse_table(raw, config)
            if caption:
                header += config.caption_template.format(caption=caption)
            summary = row_summary(cols, data, mode, config=config)
            with_summary += bool(summary)
        body = header + ((config.summary_marker + summary) if summary else "") + config.raw_marker + raw
        out.append(Document(page_content=body, metadata={**c.metadata, "raw": raw, "title": title}))
    n_table = sum(c.metadata["kind"] == "table" for c in chunks)
    return out
