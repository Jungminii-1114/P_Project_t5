"""The installed package retains the frozen parser's public contract."""

from pathlib import Path

import docparse
from tests import test_reference_generic as generic


ROOT = Path(__file__).resolve().parents[1]


def test_package_import_and_default_render():
    assert callable(docparse.run_all)
    config = docparse.ParserConfig()
    assert getattr(config, "index_render", "baseline1") == "baseline1"
    assert getattr(config, "llm_render", "baseline1") == "baseline1"


def test_installed_package_remains_generic(monkeypatch):
    monkeypatch.setattr(generic, "PACKAGE", ROOT / "src" / "docparse")
    generic.test_generic_package_has_no_forbidden_or_frozen_package_imports()
    generic.test_profile_specific_strings_are_derived_from_hardcoded_inventory()


def test_installed_profile_matches_all_snapshot_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("GACHON_DATA_DIR", str(ROOT / "data" / "dataset"))
    data_dir = generic._dataset_or_skip()
    results = docparse.run_all(data_dir, docparse.load_profile("gachon_2027"))
    from docparse.serialization import jsonl_bytes
    for stage in ("raw_docs", "chunks", "contextual_chunks"):
        snapshot = ROOT / "reference" / "baseline1" / "snapshots" / (stage + ".jsonl")
        assert snapshot.is_file(), "Regenerate the baseline snapshot before parity checks"
        expected = snapshot.read_bytes()
        normalized = [d.model_copy(update={"metadata": {
            k: v for k, v in d.metadata.items() if k != "locator"
        }}) for d in results[stage]]
        assert jsonl_bytes(normalized) == expected, stage
    assert len(results["contextual_chunks"]) == 513
