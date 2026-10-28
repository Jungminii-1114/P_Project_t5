import ast
import builtins
import hashlib
import json
import tempfile
import symtable
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.run_eval import _new_run_dir, build_run_summary, environment_record, parse_args


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "pipeline_v24.py"


def test_parser_helpers_used_by_page_index_and_grounding_remain_bound():
    symbols = symtable.symtable(PIPELINE_PATH.read_text(encoding="utf-8"), str(PIPELINE_PATH), "exec")
    for name in ("doc_title", "is_value"):
        symbol = symbols.lookup(name)
        assert symbol.is_assigned() or symbol.is_imported(), name


def test_all_pipeline_global_references_are_bound_without_importing_services():
    symbols = symtable.symtable(PIPELINE_PATH.read_text(encoding="utf-8"), str(PIPELINE_PATH), "exec")
    bound = {s.get_name() for s in symbols.get_symbols()
             if s.is_assigned() or s.is_imported() or s.is_namespace()}
    required = set()
    def walk(table):
        required.update(s.get_name() for s in table.get_symbols() if s.is_referenced() and s.is_global())
        for child in table.get_children():
            walk(child)
    walk(symbols)
    assert not required - bound - set(dir(builtins)) - {"__name__", "__file__"}


def _load_pipeline_function(name, namespace=None):
    tree = ast.parse(PIPELINE_PATH.read_text(encoding="utf-8"))
    node = next(
        item for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    scope = dict(namespace or {})
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(PIPELINE_PATH), "exec"), scope)
    return scope[name]


def _load_fallback_cache_class():
    tree = ast.parse(PIPELINE_PATH.read_text(encoding="utf-8"))
    try_node = next(
        item for item in tree.body
        if isinstance(item, ast.Try)
        and any(isinstance(child, ast.ClassDef) and child.name == "_DiskCachedEmbeddings"
                for handler in item.handlers for child in handler.body)
    )
    cache_class = next(
        child for handler in try_node.handlers for child in handler.body
        if isinstance(child, ast.ClassDef) and child.name == "_DiskCachedEmbeddings"
    )
    scope = {"Path": Path, "hashlib": hashlib, "json": json, "tempfile": tempfile}
    exec(compile(ast.Module(body=[cache_class], type_ignores=[]), str(PIPELINE_PATH), "exec"), scope)
    return scope["_DiskCachedEmbeddings"]


def _doc(source, page, kind, raw, table_id=None):
    metadata = {"source": source, "page": page, "kind": kind, "raw": raw}
    if table_id is not None:
        metadata["table_id"] = table_id
    return SimpleNamespace(metadata=metadata, page_content=raw)


def test_v24_eval_args_accept_version_variant_and_environment_settings():
    args = parse_args(["--version", "v24", "--variant", "V4", "--sets", "sample3"])

    assert args.version == "v24"
    assert args.variant == "V4"
    assert args.sets == ["sample3"]


def test_v24_eval_records_variant_and_effective_docparse_settings(tmp_path):
    pipeline = SimpleNamespace(
        manifest={},
        LLM_MODEL="gpt-test",
        EMBED_MODEL="embed-test",
        DOCPARSE_SETTINGS={
            "profile": "gachon_2027",
            "index_render": "header_records",
            "llm_render": "html_full",
            "table_full_max_chars": 12000,
        },
    )
    record = environment_record(pipeline, "v24", 2, "V4")

    assert record["variant"] == "V4"
    assert record["docparse"] == pipeline.DOCPARSE_SETTINGS
    run_dir = _new_run_dir(tmp_path, "v24", "V4")
    assert run_dir.name.endswith("_v24_V4")
    summary = build_run_summary("v24", 2, [], record)
    assert summary["variant"] == "V4"
    assert summary["docparse"] == pipeline.DOCPARSE_SETTINGS
    assert build_run_summary("v23", 1, [], record) == {
        "pipeline": "v23",
        "repeat": 1,
        "sets": {},
    }


def test_v24_eval_logs_docparse_environment_values_when_pipeline_settings_are_absent(monkeypatch):
    monkeypatch.setenv("DOCPARSE_PROFILE", "custom_profile")
    monkeypatch.setenv("DOCPARSE_INDEX_RENDER", "header_records")
    monkeypatch.setenv("DOCPARSE_LLM_RENDER", "html_full")
    record = environment_record(SimpleNamespace(manifest={}), "v24", 1)

    assert record["variant"] == "default"
    assert record["docparse"] == {
        "profile": "custom_profile",
        "index_render": "header_records",
        "llm_render": "html_full",
        "table_full_max_chars": None,
    }


def test_v24_variant_names_are_safe_for_run_folder_names():
    with pytest.raises(SystemExit):
        parse_args(["--version", "v24", "--variant", "../escape", "--sets", "sample3"])


def test_html_full_context_deduplicates_only_tables_with_full_registry_entries():
    context = _load_pipeline_function(
        "_context",
        {"DOCPARSE_LLM_RENDER": "html_full", "tables": {"table-1": "<table>full</table>"}},
    )
    result = context([
        _doc("03.pdf", 4, "table", "fragment one", "table-1"),
        _doc("03.pdf", 4, "table", "fragment two", "table-1"),
        _doc("03.pdf", 5, "text", "nearby text"),
        _doc("04.pdf", 8, "table", "oversize one", "table-large"),
        _doc("04.pdf", 8, "table", "oversize two", "table-large"),
    ])

    assert result.count("<table>full</table>") == 1
    assert "fragment one" not in result and "fragment two" not in result
    assert result.count("oversize one") == 1
    assert result.count("oversize two") == 1
    assert "nearby text" in result


def test_baseline_context_keeps_each_raw_chunk_even_if_a_table_registry_exists():
    context = _load_pipeline_function(
        "_context",
        {"DOCPARSE_LLM_RENDER": "baseline1", "tables": {"table-1": "<table>full</table>"}},
    )
    result = context([
        _doc("03.pdf", 4, "table", "fragment one", "table-1"),
        _doc("03.pdf", 4, "table", "fragment two", "table-1"),
    ])

    assert "fragment one" in result and "fragment two" in result
    assert "<table>full</table>" not in result


def test_fallback_embedding_cache_uses_model_and_text_hash_and_deduplicates_batch_misses(tmp_path):
    cache_class = _load_fallback_cache_class()

    class FakeEmbeddings:
        def __init__(self):
            self.document_calls = []
            self.query_calls = []

        def embed_documents(self, texts):
            self.document_calls.append(list(texts))
            return [[len(text), sum(text.encode("utf-8"))] for text in texts]

        def embed_query(self, text):
            self.query_calls.append(text)
            return [len(text), sum(text.encode("utf-8"))]

    backend = FakeEmbeddings()
    cache = cache_class(backend, "model-a", tmp_path)
    first = cache.embed_documents(["same text", "same text"])
    second = cache.embed_documents(["same text"])
    assert first[0] == first[1] == second[0]
    assert backend.document_calls == [["same text"]]

    other_model = cache_class(backend, "model-b", tmp_path)
    other_model.embed_documents(["same text"])
    assert backend.document_calls[-1] == ["same text"]
    assert len(backend.document_calls) == 2

    cache.embed_documents(["overlapping query text"])
    cache.embed_query("overlapping query text")
    assert backend.query_calls == ["overlapping query text"]

    assert cache.embed_query("query") == cache.embed_query("query")
    assert backend.query_calls == ["overlapping query text", "query"]


def test_chroma_documents_keep_only_scalar_metadata():
    class FakeDocument:
        def __init__(self, page_content, metadata):
            self.page_content = page_content
            self.metadata = metadata

    doc = _doc("03.pdf", 4, "table", "raw html", "table-1")
    doc.metadata["locator"] = {"type": "page", "value": 4}
    converted = _load_pipeline_function("_scalar_chroma_docs", {"Document": FakeDocument})([doc])

    assert converted[0].metadata["source"] == "03.pdf"
    assert converted[0].metadata["table_id"] == "table-1"
    assert converted[0].metadata["raw"] == "raw html"
    assert "locator" not in converted[0].metadata

