"""Portable, deterministic output serialization and provenance."""

from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

from .config import ParserConfig
from .sources import build_document_manifest


def jsonl_bytes(documents):
    lines = [json.dumps({"page_content": d.page_content, "metadata": d.metadata},
                        ensure_ascii=False, sort_keys=True, separators=(",", ":"))
             for d in documents]
    return ("\n".join(lines) + "\n").encode("utf-8") if lines else b""


def write_outputs(results, paths, out_dir, config: ParserConfig = None):
    config = config or ParserConfig()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for stage, docs in results.items():
        data = jsonl_bytes(docs)
        name = stage + ".jsonl"
        (out_dir / name).write_bytes(data)
        outputs[name] = {"records": len(docs), "sha256": hashlib.sha256(data).hexdigest()}
    by_document = {}
    for doc in results["chunks"]:
        counts = by_document.setdefault(doc.metadata["source"], {"본문": 0, "표": 0, "total": 0})
        counts["본문" if doc.metadata["kind"] == "text" else "표"] += 1
        counts["total"] += 1
    manifest = {
        "parser_version": "configurable-elements-v1",
        "configuration": asdict(config),
        "source_documents": build_document_manifest(paths, config),
        "package_versions": {name: version(name) for name in (
            "langchain-core", "langchain-text-splitters", "langchain-hwp-hwpx-loader",
            "pdfplumber", "pymupdf")},
        "counts": {"raw_documents": len(results["raw_docs"]), "chunks": len(results["chunks"]),
                   "contextual_chunks": len(results["contextual_chunks"]),
                   "by_document_and_kind": by_document},
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    return manifest
