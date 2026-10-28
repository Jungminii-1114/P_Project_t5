# baseline-1 동결 레퍼런스 — v23(64ac263) build_notebook.py §1~§4에서 이식. 수정 금지. 개선은 새 버전에서.

import argparse
import hashlib
import json
import tomllib
from pathlib import Path

from . import run_all
from .sources import build_document_manifest


LOCKED_PACKAGES = (
    "langchain-core",
    "langchain-text-splitters",
    "langchain-hwp-hwpx-loader",
    "pdfplumber",
    "pymupdf",
)


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


def _locked_versions(lock_path: Path) -> dict[str, str]:
    if not lock_path.is_file():
        return {}
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    versions = {
        package["name"].lower().replace("_", "-"): package["version"]
        for package in lock["package"]
    }
    return {name: versions[name] for name in LOCKED_PACKAGES if name in versions}


def main():
    parser = argparse.ArgumentParser(description="동결판 §1–§4 문서 파싱·청킹 CLI")
    parser.add_argument("data_dir", type=Path, help="필수 원문 5개가 있는 폴더")
    parser.add_argument("--out", type=Path, required=True, help="스냅샷 파일 출력 폴더")
    args = parser.parse_args()

    results = run_all(args.data_dir)
    args.out.mkdir(parents=True, exist_ok=True)
    output_names = {
        "raw_docs": "raw_docs.jsonl",
        "chunks": "chunks.jsonl",
        "contextual_chunks": "contextual_chunks.jsonl",
    }
    output_info = {}
    for key, filename in output_names.items():
        data = _jsonl_bytes(results[key])
        (args.out / filename).write_bytes(data)
        output_info[filename] = {
            "records": len(results[key]),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    counts_by_document = {}
    for chunk in results["chunks"]:
        source = chunk.metadata["source"]
        label = "본문" if chunk.metadata["kind"] == "text" else "표"
        per_document = counts_by_document.setdefault(source, {"본문": 0, "표": 0, "total": 0})
        per_document[label] += 1
        per_document["total"] += 1

    project_root = Path(__file__).resolve().parents[3]
    manifest = {
        "baseline": "baseline-1",
        "parser_version": "v23 (64ac263)",
        "source_documents": build_document_manifest(args.data_dir),
        "locked_packages": _locked_versions(project_root / "uv.lock"),
        "counts": {
            "raw_documents": len(results["raw_docs"]),
            "chunks": len(results["chunks"]),
            "contextual_chunks": len(results["contextual_chunks"]),
            "by_document_and_kind": counts_by_document,
        },
        "outputs": output_info,
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        "완료: "
        f"raw_docs={manifest['counts']['raw_documents']}, "
        f"chunks={manifest['counts']['chunks']}, "
        f"contextual_chunks={manifest['counts']['contextual_chunks']}"
    )


if __name__ == "__main__":
    main()
