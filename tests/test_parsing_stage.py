"""Parsing boundary tests: independent of the reference parser and all API keys."""
import json
from pathlib import Path

import pytest

from reportanchor_harness.parsing import (
    ExtractedBlock, Extraction, ParsingStage, load_parsing_artifact,
)


class DummyParser:
    identifier = "dummy"
    version = "1"
    extensions = frozenset({".pdf"})

    @property
    def settings(self):
        return {"extract_table_ir": True}

    def extract(self, path):
        return Extraction(blocks=(
            ExtractedBlock("text", "Sample text", {"type": "page", "value": 1}),
            ExtractedBlock("table", "|a|b|", {"type": "page", "value": 1},
                           table_id="table_1"),
        ), tables=({"table_id": "table_1", "cells": []},))


def test_stage_persists_and_loads_without_models(tmp_path):
    source = tmp_path / "input.pdf"
    source.write_bytes(b"sample bytes - dummy backend")
    result = ParsingStage(DummyParser()).run(source, tmp_path / "outputs")
    manifest, blocks, tables = load_parsing_artifact(result.directory)
    assert manifest["status"] == "completed"
    assert manifest["source"]["sha256"]
    assert [x["kind"] for x in blocks] == ["text", "table"]
    assert blocks[0]["pdf_page"] == 1
    assert blocks[0]["verification_status"] == "unverified"
    assert tables[0]["table_id"] == "table_1"


def test_corrupt_artifact_is_rejected(tmp_path):
    source = tmp_path / "input.pdf"
    source.write_bytes(b"input")
    result = ParsingStage(DummyParser()).run(source, tmp_path / "outputs")
    (result.directory / "blocks.jsonl").write_text("corruption\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        load_parsing_artifact(result.directory)


def test_failed_parser_run_records_status(tmp_path):
    class BrokenParser(DummyParser):
        def extract(self, path):
            raise RuntimeError("broken")
    source = tmp_path / "input.pdf"
    source.write_bytes(b"input")
    root = tmp_path / "outputs"
    with pytest.raises(RuntimeError, match="broken"):
        ParsingStage(BrokenParser()).run(source, root)
    [run_dir] = root.iterdir()
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert state["error_type"] == "RuntimeError"


def test_unsupported_input_rejected(tmp_path):
    source = tmp_path / "input.txt"
    source.write_text("text", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        ParsingStage(DummyParser()).run(source, tmp_path / "outputs")
