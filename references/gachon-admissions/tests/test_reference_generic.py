import ast
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys

import pymupdf
import pytest

from reference.baseline1.docparse_generic import ParserConfig, load_sources, run_all


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "reference" / "baseline1" / "docparse_generic"
FROZEN_CONTEXTUAL = ROOT / "reference" / "baseline1" / "snapshots" / "contextual_chunks.jsonl"
HARDCODED = PACKAGE / "HARDCODED.md"
API_KEYS = ("OPENAI_API_KEY", "VOYAGEAI_API_KEY", "VOYAGE_API_KEY")
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
GACHON_FILES = (
    "01_2027학년도_재외국민_모집요강.hwp",
    "02_2027학년도_지역의사선발전형_안내.pdf",
    "03_2027학년도_수시_모집요강.pdf",
    "04_2027학년도_정시_모집요강.pdf",
    "05_2027학년도_수시_면접고사_일정.pdf",
)


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    """Fail locally if a parser or imported dependency attempts outbound I/O."""
    def blocked(*args, **kwargs):
        raise RuntimeError("Network access is disabled in generic parser tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket.socket, "sendto", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


def _write_pdf(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(str(path))
    document.close()
    return path


def _read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _api_free_environment(import_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    for key in API_KEYS:
        environment.pop(key, None)
    environment["PYTHONPATH"] = str(import_root)
    return environment


def _install_subprocess_network_guard(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "sitecustomize.py").write_text(
        "\n".join((
            "import os",
            "import socket",
            "",
            "for _name in ('OPENAI_API_KEY', 'VOYAGEAI_API_KEY', 'VOYAGE_API_KEY'):",
            "    if os.environ.get(_name):",
            "        raise RuntimeError('API credentials must be absent in parser tests')",
            "",
            "def _blocked(*args, **kwargs):",
            "    raise RuntimeError('Network access is disabled in parser tests')",
            "",
            "socket.socket.connect = _blocked",
            "socket.socket.connect_ex = _blocked",
            "socket.socket.sendto = _blocked",
            "socket.create_connection = _blocked",
            "",
        )),
        encoding="utf-8",
    )


def _run_cli(module: str, paths, output_dir: Path, *, cwd: Path, environment: dict[str, str], profile=None):
    command = [sys.executable, "-m", module]
    command.extend(str(path) for path in paths)
    if profile is not None:
        command.extend(("--profile", str(profile)))
    command.extend(("--out", str(output_dir)))
    return subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True, check=False)


def _dataset_or_skip() -> Path:
    value = os.environ.get("GACHON_DATA_DIR")
    if not value or not Path(value).is_dir():
        pytest.skip("GACHON_DATA_DIR이 없거나 디렉터리가 아닙니다")
    data_dir = Path(value)
    missing = [name for name in GACHON_FILES if not (data_dir / name).is_file()]
    if missing:
        pytest.skip("GACHON_DATA_DIR에 필수 원문 5개가 없습니다")
    return data_dir


def _assert_cli_succeeded(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _import_roots(tree: ast.AST) -> set[str]:
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_generic_package_has_no_forbidden_or_frozen_package_imports():
    violations = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in sorted(_import_roots(tree) & FORBIDDEN_IMPORTS):
            violations.append(f"{path.relative_to(PACKAGE)}: forbidden import {name}")
        for node in ast.walk(tree):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
            if (module and "docparse_b1" in module.split(".")) or any(
                "docparse_b1" in name.split(".") for name in names
            ):
                violations.append(f"{path.relative_to(PACKAGE)}: imports frozen package")
    assert not violations, "\n".join(violations)


def test_profile_specific_strings_are_derived_from_hardcoded_inventory():
    hardcoded = HARDCODED.read_text(encoding="utf-8")
    section = hardcoded.split("## 범용 소스 문자열 금지 목록", 1)[-1]
    block = re.search(r"```text\s*(.*?)```", section, flags=re.DOTALL)
    assert block, "HARDCODED.md에 금지 문자열 코드 블록이 없습니다"
    banned = [line.strip() for line in block.group(1).splitlines() if line.strip()]
    assert banned, "HARDCODED.md 금지 문자열 목록이 비어 있습니다"

    violations = []
    generic_sources = [
        path for path in sorted(PACKAGE.rglob("*.py"))
        if "profiles" not in path.relative_to(PACKAGE).parts
    ]
    for path in generic_sources:
        source = path.read_text(encoding="utf-8")
        for value in banned:
            if value in source:
                violations.append(f"{path.relative_to(PACKAGE)} contains {value!r}")
    assert not violations, "프로필 밖에 특화 문자열이 있습니다:\n" + "\n".join(violations)


def test_load_sources_accepts_file_directory_glob_and_optional_requirements(tmp_path):
    documents = tmp_path / "inputs"
    first = _write_pdf(documents / "alpha.pdf", "first local file")
    second = _write_pdf(documents / "beta.pdf", "second local file")
    third = _write_pdf(documents / "gamma.pdf", "third local file")

    assert [path.name for path in load_sources(first)] == ["alpha.pdf"]
    assert [path.name for path in load_sources(documents)] == ["alpha.pdf", "beta.pdf", "gamma.pdf"]
    assert [path.name for path in load_sources(str(documents / "*.pdf"))] == [
        "alpha.pdf", "beta.pdf", "gamma.pdf"
    ]
    required = ParserConfig(required_files=("gamma.pdf", "alpha.pdf"))
    assert [path.name for path in load_sources(documents, required)] == ["gamma.pdf", "alpha.pdf"]
    with pytest.raises(FileNotFoundError, match="missing.pdf"):
        load_sources(documents, ParserConfig(required_files=("missing.pdf",)))


def test_neutral_public_api_parses_an_unrelated_generated_pdf(tmp_path):
    phrase = "Portable generic parser smoke test 8675309."
    pdf = _write_pdf(tmp_path / "unrelated-document.pdf", phrase)

    result = run_all(pdf)

    assert set(result) == {"raw_docs", "chunks", "contextual_chunks"}
    assert result["raw_docs"]
    assert any(phrase in document.page_content for document in result["raw_docs"])
    assert any(document.metadata["kind"] == "text" for document in result["chunks"])
    assert any(phrase in document.page_content for document in result["contextual_chunks"])


def test_generic_folder_copy_imports_and_cli_runs_from_another_directory(tmp_path):
    isolated_root = tmp_path / "isolated_runtime"
    copied_package = isolated_root / "docparse_generic"
    shutil.copytree(PACKAGE, copied_package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    _install_subprocess_network_guard(isolated_root)
    outside_cwd = tmp_path / "outside"
    outside_cwd.mkdir()
    phrase = "Standalone copied parser smoke test 314159."
    pdf = _write_pdf(tmp_path / "input" / "portable.pdf", phrase)
    environment = _api_free_environment(isolated_root)

    imported = subprocess.run(
        [sys.executable, "-c", "import docparse_generic; assert callable(docparse_generic.run_all)"],
        cwd=outside_cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    _assert_cli_succeeded(imported)

    output = tmp_path / "isolated-output"
    completed = _run_cli(
        "docparse_generic", [pdf], output, cwd=outside_cwd, environment=environment
    )
    _assert_cli_succeeded(completed)
    chunks = _read_jsonl(output / "chunks.jsonl")
    assert any(record["metadata"]["kind"] == "text" for record in chunks)
    assert any(phrase in record["page_content"] for record in chunks)


def test_gachon_profile_contextual_chunks_match_frozen_snapshot(tmp_path):
    data_dir = _dataset_or_skip()
    if not FROZEN_CONTEXTUAL.is_file():
        pytest.skip("동결판 contextual_chunks.jsonl 스냅샷이 없습니다")

    guard_dir = tmp_path / "guard"
    _install_subprocess_network_guard(guard_dir)
    output = tmp_path / "gachon-profile"
    result = _run_cli(
        "reference.baseline1.docparse_generic",
        [data_dir],
        output,
        cwd=ROOT,
        environment=_api_free_environment(guard_dir),
        profile="gachon_2027",
    )
    _assert_cli_succeeded(result)

    actual = _read_jsonl(output / "contextual_chunks.jsonl")
    expected = _read_jsonl(FROZEN_CONTEXTUAL)
    assert len(expected) == 513
    assert len(actual) == len(expected) == 513

    def without_locator(record):
        return {
            "page_content": record["page_content"],
            "metadata": {key: value for key, value in record["metadata"].items() if key != "locator"},
        }

    for index, (actual_record, expected_record) in enumerate(zip(actual, expected)):
        normalized_actual = without_locator(actual_record)
        normalized_expected = without_locator(expected_record)
        if normalized_actual != normalized_expected:
            pytest.fail(
                f"가천대 프로필 스냅샷 불일치 at contextual chunk {index}: "
                f"actual metadata={normalized_actual['metadata']!r}; "
                f"expected metadata={normalized_expected['metadata']!r}"
            )
    assert all("locator" in record["metadata"] for record in actual)


def test_neutral_profile_completes_on_the_same_five_documents(tmp_path):
    data_dir = _dataset_or_skip()
    guard_dir = tmp_path / "guard"
    _install_subprocess_network_guard(guard_dir)
    output = tmp_path / "neutral-profile"
    result = _run_cli(
        "reference.baseline1.docparse_generic",
        [data_dir],
        output,
        cwd=ROOT,
        environment=_api_free_environment(guard_dir),
        profile="neutral",
    )
    _assert_cli_succeeded(result)

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["source_documents"]) == set(GACHON_FILES)
    assert manifest["configuration"]["required_files"] == []
    assert manifest["counts"]["raw_documents"] > 0
    assert manifest["counts"]["chunks"] > 0
    assert manifest["counts"]["contextual_chunks"] > 0
