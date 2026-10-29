"""Adapter for the frozen admissions reference parser on the JS branch.

This is an integration bridge, not a replacement for the reference RAG.
The reference parser runs without embedding or LLM API calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .parsing import Extraction, ExtractedBlock


@dataclass
class LegacyDocparseAdapter:
    identifier: str = "gachon-docparse"
    version: str = "v24-parser"
    extensions: frozenset[str] = frozenset({".pdf", ".hwp"})
    profile: str = "neutral"
    overrides: dict = field(default_factory=lambda: {"extract_table_ir": True})

    @property
    def settings(self) -> dict:
        return {"profile": self.profile, "overrides": self.overrides}

    def extract(self, path: Path) -> Extraction:
        try:
            import docparse
        except ImportError as exc:
            raise RuntimeError(
                "Install the reference docparse package or add its src directory "
                "to PYTHONPATH before using LegacyDocparseAdapter"
            ) from exc
        from dataclasses import replace

        config = replace(docparse.load_profile(self.profile), **self.overrides)
        # parse_files intentionally skips chunking, embeddings and retrieval.
        table_registry = {}
        docs = docparse.parse_files(path, config, tables=table_registry)
        blocks = []
        for doc in docs:
            kind = doc.metadata["kind"]
            blocks.append(ExtractedBlock(
                kind=kind,
                text=doc.page_content,
                locator=doc.metadata["locator"],
                table_id=doc.metadata.get("table_id"),
            ))
        return Extraction(
            blocks=tuple(blocks),
            tables=tuple(table.to_dict() for table in table_registry.values()),
        )
