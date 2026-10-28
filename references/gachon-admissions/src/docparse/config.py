"""Parser settings; defaults contain no document or industry vocabulary."""

from dataclasses import dataclass, field
from importlib import import_module
import json
from pathlib import Path


@dataclass
class ParserConfig:
    index_render: str = "baseline1"
    llm_render: str = "baseline1"
    extract_table_ir: bool = False
    table_full_max_chars: int = 12000
    ir_coord_tolerance: float = 0.5
    ir_max_header_rows: int = 8
    required_files: tuple[str, ...] = ()
    title_map: dict[str, str] = field(default_factory=dict)
    title_prefix_length: int | None = None
    title_fallback_source: bool = False
    title_cleanup_pattern: str = r"^\d+[\s_-]*"
    header_keywords: tuple[str, ...] = ()
    row_label_keywords: tuple[str, ...] = ()
    excluded_columns: tuple[str, ...] = ()
    schedule_pattern: str = ""
    schedule_caption: str = ""
    generic_columns: tuple[str, ...] = ()
    value_symbols: tuple[str, ...] = ("O", "■", "□", "△", "○", "●", "X", "▲", "★", "◉")
    numeric_pattern: str = r"^[\d,./~%()~\-–\s]+$"
    wide_min_columns: int = 7
    normalize_date_dots: bool = True
    whitespace_pattern: str = r"[ \t]+"
    date_dot_pattern: str = r"(?<=\d)\s*\.\s*(?=\d)"
    separators: tuple[str, ...] = ("\n\n", "\n", ". ", "다. ", " ", "")
    chunk_size: int = 800
    chunk_overlap: int = 100
    table_max_chars: int = 1400
    merged_repeat_max_chars: int = 40
    pdf_table_min_chars: int = 60
    summary_max_rows: int = 30
    summary_max_chars: int = 2600
    summary_max_pairs: int = 6
    caption_max_chars: int = 30
    chunk_prefix_template: str = "[{source} p.{page}]\n"
    context_header_template: str = "[문서] {title} | p.{page} | {kind_label}"
    caption_template: str = " | 표제: {caption}"
    kind_labels: dict[str, str] = field(default_factory=lambda: {"text": "본문", "table": "표"})
    summary_marker: str = "\n[표 행 요약]\n"
    raw_marker: str = "\n[원문]\n"
    note_prefix: str = "※"
    hwp_marker_pattern: str = r"\[(?:rowspan=\d+,\s*colspan=\d+|colspan=\d+,\s*rowspan=\d+|merged:[^\]]+)\]"
    image_marker: str = "[IMAGE]"
    hwp_mode: str = "elements"
    hwp_distribution_backend: str = "pyhwp"

    def __post_init__(self):
        if self.index_render not in {"baseline1", "header_records"}:
            raise ValueError("Invalid index_render")
        if self.llm_render not in {"baseline1", "html_full", "header_records"}:
            raise ValueError("Invalid llm_render")
        if self.table_full_max_chars < 1 or self.ir_coord_tolerance <= 0:
            raise ValueError("Table limits must be positive")

    @property
    def ir_enabled(self):
        return self.extract_table_ir or self.index_render != "baseline1" or self.llm_render != "baseline1"


def load_profile(name_or_path: str | Path | None = None) -> ParserConfig:
    """Load a built-in profile name or a JSON file containing dataclass fields."""
    if name_or_path is None or str(name_or_path) == "neutral":
        return ParserConfig()
    path = Path(name_or_path)
    if path.is_file():
        return ParserConfig(**json.loads(path.read_text(encoding="utf-8")))
    # Profile names are module names, never filesystem paths or expressions.
    name = str(name_or_path)
    if not name.isidentifier():
        raise ValueError("Profile must be a module name or an existing JSON path")
    return import_module(f"{__package__}.profiles.{name}").CONFIG
