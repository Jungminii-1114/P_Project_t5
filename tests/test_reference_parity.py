import ast
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "reference" / "baseline1" / "docparse_b1"
SNAPSHOTS = ROOT / "reference" / "baseline1" / "snapshots"
JSONL_NAMES = ("raw_docs.jsonl", "chunks.jsonl", "contextual_chunks.jsonl")
FORBIDDEN_IMPORTS = {
    "langchain_openai",
    "openai",
    "voyageai",
    "langchain_voyageai",
    "chromadb",
    "langchain_chroma",
    "rank_bm25",
    "kiwipiepy",
}


def _import_roots(tree):
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_frozen_package_has_no_forbidden_direct_imports():
    violations = []
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in sorted(_import_roots(tree) & FORBIDDEN_IMPORTS):
            violations.append(f"{path.name}: {name}")
    assert not violations, "금지 의존성을 직접 import합니다: " + ", ".join(violations)


def test_cli_jsonl_matches_reference_snapshot(tmp_path):
    data_dir_value = os.environ.get("GACHON_DATA_DIR")
    required_files = (
        "01_2027학년도_재외국민_모집요강.hwp",
        "02_2027학년도_지역의사선발전형_안내.pdf",
        "03_2027학년도_수시_모집요강.pdf",
        "04_2027학년도_정시_모집요강.pdf",
        "05_2027학년도_수시_면접고사_일정.pdf",
    )
    if not data_dir_value or not Path(data_dir_value).is_dir():
        pytest.skip("GACHON_DATA_DIR이 없거나 디렉터리가 아닙니다")
    if not all((Path(data_dir_value) / name).is_file() for name in required_files):
        pytest.skip("GACHON_DATA_DIR에 필수 원문 5개가 없습니다")
    if not all((SNAPSHOTS / name).is_file() for name in JSONL_NAMES):
        pytest.skip("기준 JSONL 스냅샷이 없습니다")

    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    environment.pop("VOYAGEAI_API_KEY", None)
    environment["GACHON_DATA_DIR"] = data_dir_value
    result_dir = tmp_path / "docparse-b1-cli"
    command = [
        sys.executable,
        "-m",
        "reference.baseline1.docparse_b1",
        data_dir_value,
        "--out",
        str(result_dir),
    ]
    subprocess.run(command, cwd=ROOT, env=environment, check=True, capture_output=True, text=True)

    for name in JSONL_NAMES:
        assert (result_dir / name).read_bytes() == (SNAPSHOTS / name).read_bytes(), name
    assert (result_dir / "manifest.json").read_bytes() == (SNAPSHOTS / "manifest.json").read_bytes()

    import json

    manifest = json.loads((result_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["contextual_chunks"] == 513
