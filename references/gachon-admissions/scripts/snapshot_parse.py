"""Create the v23 section 1–4 parsing snapshot without importing the builder."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "build_notebook.py"
SNAPSHOT_DIR = ROOT / "reference" / "baseline1" / "snapshots"
LOCKED_PACKAGES = (
    "langchain-core",
    "langchain-text-splitters",
    "langchain-hwp-hwpx-loader",
    "pdfplumber",
    "pymupdf",
)


def _builder_cells(path: Path = BUILDER):
    """Read the builder's literal md()/code() calls without executing its writer."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    cells = []
    for statement in tree.body:
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            continue
        call = statement.value
        if not isinstance(call.func, ast.Name) or call.func.id not in {"md", "code"}:
            continue
        if not call.args:
            continue
        value = ast.literal_eval(call.args[0])
        cells.append(("markdown" if call.func.id == "md" else "code", value.strip("\n")))
    return cells


def _section_1_to_4_code_cells(cells):
    """Select code cells between markdown headings ## 1. and ## 5."""
    active_section = None
    selected = []
    for cell_type, source in cells:
        if cell_type == "markdown":
            match = re.search(r"(?m)^##\s+(\d+)\.", source)
            if match:
                active_section = int(match.group(1))
        elif cell_type == "code" and active_section is not None and 1 <= active_section <= 4:
            selected.append((active_section, source))
    sections = {section for section, _ in selected}
    missing = {1, 2, 3, 4} - sections
    if missing:
        raise RuntimeError(f"build_notebook.py에서 파싱 코드 섹션을 찾지 못했습니다: {sorted(missing)}")
    return selected


def _jsonl_bytes(documents) -> bytes:
    lines = [
        json.dumps(
            {"page_content": doc.page_content, "metadata": doc.metadata},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for doc in documents
    ]
    return ("\n".join(lines) + "\n").encode("utf-8") if lines else b""


def _write_jsonl(path: Path, documents) -> tuple[int, str]:
    data = _jsonl_bytes(documents)
    path.write_bytes(data)
    return len(documents), hashlib.sha256(data).hexdigest()


def _locked_versions(lock_path: Path) -> dict[str, str]:
    if not lock_path.is_file():
        return {}
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    versions = {
        package["name"].lower().replace("_", "-"): package["version"]
        for package in lock["package"]
    }
    return {name: versions[name] for name in LOCKED_PACKAGES if name in versions}


def create_snapshot(data_dir: Path, out_dir: Path = SNAPSHOT_DIR):
    data_dir = data_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    # The source cell's local-only loader uses this path; when set, it raises on
    # missing files and never searches Colab, Drive, ZIP files, or uploads.
    os.environ["GACHON_DATA_DIR"] = str(data_dir)

    namespace = {"__name__": "__snapshot_parse__"}
    for section, source in _section_1_to_4_code_cells(_builder_cells()):
        filename = f"build_notebook.py:section-{section}"
        exec(compile(source, filename, "exec"), namespace)

    outputs = {
        "raw_docs.jsonl": namespace["raw_docs"],
        "chunks.jsonl": namespace["chunks"],
        "contextual_chunks.jsonl": namespace["chunks_ctx"],
    }
    output_info = {}
    for filename, documents in outputs.items():
        count, digest = _write_jsonl(out_dir / filename, documents)
        output_info[filename] = {"records": count, "sha256": digest}

    counts_by_document = {}
    for chunk in outputs["chunks.jsonl"]:
        source = chunk.metadata["source"]
        kind = chunk.metadata["kind"]
        label = "본문" if kind == "text" else "표"
        per_document = counts_by_document.setdefault(source, {"본문": 0, "표": 0, "total": 0})
        per_document[label] += 1
        per_document["total"] += 1

    manifest = {
        "baseline": "baseline-1",
        "parser_version": "v23 (64ac263)",
        "source_documents": namespace["build_document_manifest"](data_dir),
        "locked_packages": _locked_versions(ROOT / "uv.lock"),
        "counts": {
            "raw_documents": len(outputs["raw_docs.jsonl"]),
            "chunks": len(outputs["chunks.jsonl"]),
            "contextual_chunks": len(outputs["contextual_chunks.jsonl"]),
            "by_document_and_kind": counts_by_document,
        },
        "outputs": output_info,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description="v23 §1–§4 파싱 스냅샷 생성 (API 사용 없음)")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("GACHON_DATA_DIR", ROOT / "data" / "dataset")),
        help="5개 원문 파일이 있는 폴더 (기본값: GACHON_DATA_DIR 또는 data/dataset)",
    )
    parser.add_argument("--out", type=Path, default=SNAPSHOT_DIR, help="스냅샷 출력 폴더")
    args = parser.parse_args()
    manifest = create_snapshot(args.data_dir, args.out)
    print(
        "스냅샷 완료: "
        f"raw_docs={manifest['counts']['raw_documents']}, "
        f"chunks={manifest['counts']['chunks']}, "
        f"contextual_chunks={manifest['counts']['contextual_chunks']}"
    )
    for name, item in manifest["outputs"].items():
        print(f"{name}: {item['sha256']}")


if __name__ == "__main__":
    main()
