"""Structural contracts use synthetic tables; source goldens are audited separately."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from docparse import ParserConfig
from docparse.ir import Cell, Table, table_id
from docparse.render import baseline1, chroma_metadata, header_records, html_full, split_records
from docparse.table_ir import infer_structure


@pytest.fixture
def merged_table():
    return infer_structure(Table("example", "unrelated.pdf", {"type": "page", "value": 1},
        1, 5, 3, [Cell(0, 0, 2, 1, "Item"), Cell(0, 1, 1, 2, "Window"),
        Cell(1, 1, text="First"), Cell(1, 2, text="Second"),
        Cell(2, 0, 2, 1, "Alpha"), Cell(2, 1, text="10"), Cell(2, 2, text="20"),
        Cell(3, 1, text="30"), Cell(3, 2, text="40"),
        Cell(4, 0, text="Beta"), Cell(4, 1, text="50"), Cell(4, 2, text="60")]))


def test_json_round_trip_and_merged_paths(merged_table):
    table = Table.from_json(merged_table.to_json())
    assert table == merged_table
    assert (table.header_rows, table.stub_cols, table.confidence) == (2, 1, "confident")
    assert table.header_path(2) == ["Window", "Second"]
    assert table.row_label(3) == ["Alpha"]
    assert table_id("a.pdf", {"type": "page", "value": 2}, 0) == table_id(
        "a.pdf", {"value": 2, "type": "page"}, 0)
    assert table_id("a.pdf", {}, 0) != table_id("a.pdf", {}, 1)


def test_render_formats_and_split_paths(merged_table):
    rendered = html_full(merged_table)
    assert 'rowspan="2"' in rendered and 'colspan="2"' in rendered
    assert rendered.startswith("<table>") and rendered.endswith("</table>")
    records = header_records(merged_table)
    assert records[0] == (2, "[Alpha] Window/First = 10")
    shards = split_records(merged_table, 45)
    assert len(shards) > 1
    assert [record for shard in shards for record in shard] == records
    assert all("Window/" in line and " = " in line for shard in shards for _, line in shard)
    assert "|---|" in baseline1(merged_table)
    assert "Alpha" in html_full(merged_table, [3])


def test_invalid_geometry_and_modes():
    with pytest.raises(ValueError):
        Table("x", "a", {}, 1, 1, 1, [Cell(0, 0, 2, 1)])
    with pytest.raises(ValueError):
        ParserConfig(index_render="html_full")
    assert chroma_metadata({"locator": {}, "ir": [], "table_id": "x", "page": 1}) == {
        "table_id": "x", "page": 1}


def test_horizontal_row_label_is_not_a_header_band():
    table = infer_structure(Table("merged-label", "a.pdf", {}, 1, 2, 3, [
        Cell(0, 0, 1, 2, "Name"), Cell(0, 2, text="Count"),
        Cell(1, 0, 1, 2, "Alpha"), Cell(1, 2, text="10")]))
    assert table.header_rows == 1
    assert table.stub_cols == 2


def test_missing_pdf_geometry_uses_unmerged_fallback():
    from docparse.extract_ir import pdf_table
    table = pdf_table(None, None, [["Item", "Count"], ["Alpha", "10"]],
                      "portable.pdf", 1, 0, ParserConfig())
    assert table.origin == "pdf_fallback"
    assert (table.n_rows, table.n_cols) == (2, 2)
    assert all(c.rowspan == c.colspan == 1 for c in table.cells)
    assert table.header_path(1) == ["Count"]
    assert table.row_label(1) == ["Alpha"]


def test_source_golden_comparison_reports_failures(merged_table):
    from scripts.check_table_golden import compare_table
    expected = {"id": "synthetic", "source": "unrelated.pdf", "page": 1, "type": "merged",
        "expected": {"header_rows": 2, "stub_cols": 1, "samples": [{
            "coordinate": [2, 1], "row_label": ["Alpha"],
            "header_path": ["Window", "First"], "value": "10"}]}}
    assert compare_table(expected, merged_table)["passed"]
    expected["expected"]["samples"][0]["value"] = "999"
    failure = compare_table(expected, merged_table)
    assert not failure["passed"]
    assert failure["samples"][0]["checks"] == {"row_label": True, "header_path": True, "value": False}


def test_source_golden_corpus_is_compared_without_rewriting_expectations():
    from scripts.check_table_golden import compare
    root = Path(__file__).resolve().parents[1]
    ir = root / "runs/baseline2/ir/table_ir.jsonl"
    if not ir.exists():
        pytest.skip("Generate saved IR with the documented parser-only command")
    golden = root / "tests/golden/tables.yaml"
    before = golden.read_bytes()
    result = compare(golden, ir)
    assert golden.read_bytes() == before
    assert 8 <= result["summary"]["tables_total"] <= 12
    assert result["summary"]["cells_total"] >= 5 * result["summary"]["tables_total"]
    assert result["all_passed"] == all(table["passed"] for table in result["tables"])


def test_uncertain_table_retains_baseline_output():
    from langchain_core.documents import Document
    from docparse.chunk import chunk_documents
    from docparse.context import build_contextual_chunks
    from docparse.render import render_chunks
    table = infer_structure(Table("unknown", "a.pdf", {}, 1, 2, 2,
        [Cell(0, 0, text="10"), Cell(0, 1, text="20"),
         Cell(1, 0, text="30"), Cell(1, 1, text="40")]))
    assert table.confidence == "uncertain"
    raw = [Document(page_content="| 10 | 20 |\n|---|---|\n| 30 | 40 |", metadata={
        "source": "a.pdf", "page": 1, "kind": "table", "table_id": table.table_id})]
    config = ParserConfig(index_render="header_records", llm_render="html_full")
    chunks = chunk_documents(raw, config)
    contextual = build_contextual_chunks(chunks, config)
    _, actual, full = render_chunks(raw, chunks, contextual, {table.table_id: table}, config)
    assert actual == contextual
    assert full == {}


def test_index_bytes_independent_of_html_evidence(merged_table):
    from langchain_core.documents import Document
    from docparse.chunk import chunk_documents
    from docparse.context import build_contextual_chunks
    from docparse.render import render_chunks
    config = ParserConfig()
    raw = [Document(page_content=baseline1(merged_table), metadata={
        "source": "unrelated.pdf", "page": 1, "kind": "table", "table_id": "example"})]
    chunks = chunk_documents(raw, config)
    old = build_contextual_chunks(chunks, config)
    _, actual, full = render_chunks(raw, chunks, old, {"example": merged_table},
        replace(config, llm_render="html_full"))
    assert [d.page_content for d in old] == [d.page_content for d in actual]
    assert actual[0].metadata["raw"].endswith("</table>")
    assert "example" in full
    _, _, bounded = render_chunks(raw, chunks, old, {"example": merged_table},
        replace(config, llm_render="html_full", table_full_max_chars=1))
    assert bounded == {}
