"""Document parsing boundary: no RAG, embeddings, or model execution.

This module is deliberately dependency-free. Backends perform extraction;
the stage validates the result and persists an immutable run artifact.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4
import json


SCHEMA_VERSION = "reportanchor.parsed-document.v1"


@dataclass(frozen=True)
class ExtractedBlock:
    kind: Literal["text", "table"]
    text: str
    locator: dict[str, Any]
    table_id: str | None = None


@dataclass(frozen=True)
class Extraction:
    blocks: tuple[ExtractedBlock, ...]
    # The backend can provide provisional table geometry / IR. It is NOT a
    # validated interpretation of row labels, column headers, or values.
    tables: tuple[dict[str, Any], ...] = ()


class ParserBackend(Protocol):
    identifier: str
    version: str
    extensions: frozenset[str]

    @property
    def settings(self) -> dict[str, Any]: ...

    def extract(self, path: Path) -> Extraction: ...


@dataclass(frozen=True)
class ParseRun:
    directory: Path
    manifest: dict[str, Any]


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_bytes(_canonical(value) + b"\n")


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    return b"".join(_canonical(record) + b"\n" for record in records)


def _check_locator(locator: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(locator, dict):
        raise ValueError("Each block needs an explicit source locator")
    kind, value = locator.get("type"), locator.get("value")
    if kind not in {"page", "element_index"} or type(value) is not int:
        raise ValueError("Unsupported or malformed source locator")
    if value < (1 if kind == "page" else 0):
        raise ValueError("Invalid locator offset")
    # Restrict to a small, typed contract; do not inherit arbitrary metadata.
    return {"type": kind, "value": value}


def _validate(extraction: Extraction) -> None:
    if not isinstance(extraction, Extraction):
        raise TypeError("ParserBackend must return Extraction")
    table_ids: set[str] = set()
    for table in extraction.tables:
        if not isinstance(table, dict):
            raise TypeError("Table IR must be a JSON-compatible object")
        key = table.get("table_id")
        if not isinstance(key, str) or not key or key in table_ids:
            raise ValueError("Table IR needs a unique non-empty table_id")
        table_ids.add(key)
        _canonical(table)
    for block in extraction.blocks:
        if not isinstance(block, ExtractedBlock):
            raise TypeError("Invalid extracted block type")
        if block.kind not in {"text", "table"}:
            raise ValueError("Only text and table blocks are supported in v1")
        if not isinstance(block.text, str) or not block.text.strip():
            raise ValueError("Extracted block has no text")
        _check_locator(block.locator)
        if block.table_id is not None and block.table_id not in table_ids:
            raise ValueError("A block refers to an absent table IR")


class ParsingStage:
    """Execute one document extraction and persist independently usable outputs.

    The output is an immutable per-run directory. No prior artifact is reused
    implicitly: caching and replay are separate future harness concerns.
    """

    def __init__(self, backend: ParserBackend):
        self.backend = backend

    def run(self, source_path: str | Path, output_root: str | Path) -> ParseRun:
        path = Path(source_path).expanduser().resolve(strict=True)
        if not path.is_file():
            raise ValueError("Document source is not a regular file")
        if path.suffix.lower() not in self.backend.extensions:
            raise ValueError("Unsupported document type for selected backend")

        settings = self.backend.settings
        settings_hash = sha256(_canonical(settings)).hexdigest()
        source_hash = _sha256_file(path)
        size = path.stat().st_size
        document_id = "doc_" + sha256(
            _canonical([path.name, source_hash])
        ).hexdigest()[:24]

        run_id = "parse_" + uuid4().hex
        directory = Path(output_root) / run_id
        directory.mkdir(parents=True, exist_ok=False)
        _write_json(directory / "state.json", {
            "run_id": run_id, "stage": "document_parsing", "status": "running",
        })
        try:
            extraction = self.backend.extract(path)
            _validate(extraction)
            if _sha256_file(path) != source_hash:
                raise RuntimeError("Source changed during document parsing")

            blocks: list[dict[str, Any]] = []
            for order, block in enumerate(extraction.blocks):
                loc = _check_locator(block.locator)
                block_id = "blk_" + sha256(_canonical([
                    document_id, self.backend.identifier,
                    self.backend.version, settings_hash, order,
                ])).hexdigest()[:24]
                blocks.append({
                    "block_id": block_id,
                    "document_id": document_id,
                    "order": order,
                    "kind": block.kind,
                    "text": block.text,
                    "text_sha256": sha256(block.text.encode("utf-8")).hexdigest(),
                    "locator": loc,
                    # HWP element indexes must not be presented as printed pages.
                    "pdf_page": loc["value"] if loc["type"] == "page"
                    and path.suffix.lower() == ".pdf" else None,
                    "table_id": block.table_id,
                    "verification_status": "unverified",
                })

            tables = [
                {"document_id": document_id, "table_id": table["table_id"],
                 "ir": table, "verification_status": "unverified"}
                for table in extraction.tables
            ]
            contents = {
                "blocks.jsonl": _jsonl_bytes(blocks),
                "tables.jsonl": _jsonl_bytes(tables),
            }
            outputs = {}
            for name, data in contents.items():
                (directory / name).write_bytes(data)
                outputs[name] = {
                    "sha256": sha256(data).hexdigest(),
                    "records": len(blocks) if name == "blocks.jsonl" else len(tables),
                }
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "stage": "document_parsing",
                "status": "completed",
                "source": {
                    "document_id": document_id,
                    "filename": path.name,
                    "format": path.suffix.lower().lstrip("."),
                    "sha256": source_hash,
                    "size_bytes": size,
                },
                "backend": {
                    "identifier": self.backend.identifier,
                    "version": self.backend.version,
                    "settings_sha256": settings_hash,
                    "settings": settings,
                },
                "outputs": outputs,
            }
            _write_json(directory / "manifest.json", manifest)
            _write_json(directory / "state.json", {
                "run_id": run_id, "stage": "document_parsing", "status": "completed",
            })
            return ParseRun(directory=directory, manifest=manifest)
        except Exception as exc:
            # Do not leak source contents or local absolute paths in failure logs.
            _write_json(directory / "state.json", {
                "run_id": run_id, "stage": "document_parsing",
                "status": "failed", "error_type": type(exc).__name__,
            })
            raise


def load_parsing_artifact(directory: str | Path) -> tuple[dict[str, Any], list[dict], list[dict]]:
    """Read a successful parse run and verify stored file hashes/counts."""
    directory = Path(directory)
    state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
    if state.get("status") != "completed":
        raise ValueError("Parsing run has not completed")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "completed":
        raise ValueError("Unsupported or incomplete parsing manifest")
    results = []
    for filename in ("blocks.jsonl", "tables.jsonl"):
        data = (directory / filename).read_bytes()
        spec = manifest["outputs"][filename]
        if sha256(data).hexdigest() != spec["sha256"]:
            raise ValueError("Artifact checksum mismatch: " + filename)
        rows = [json.loads(line) for line in data.decode("utf-8").splitlines()]
        if len(rows) != spec["records"]:
            raise ValueError("Artifact record count mismatch: " + filename)
        results.append(rows)
    return manifest, results[0], results[1]
