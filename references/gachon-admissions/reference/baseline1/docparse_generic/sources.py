"""Deterministic local file, directory, and glob inputs."""

import glob
import hashlib
from pathlib import Path

from .config import ParserConfig

PARSER_VERSIONS = {".hwp": "hwp-elements-pyhwp-v1", ".pdf": "pymupdf-text-pdfplumber-v1"}


def load_sources(paths, config: ParserConfig = None):
    config = config or ParserConfig()
    if isinstance(paths, (str, Path)):
        paths = [paths]
    found = []
    seen = set()
    for entry in paths:
        path = Path(entry).expanduser()
        if path.is_dir():
            matches = sorted((p for p in path.iterdir() if p.is_file()
                              and p.suffix.lower() in PARSER_VERSIONS), key=lambda p: p.as_posix())
        elif path.is_file():
            matches = [path]
        else:
            matches = sorted((Path(p) for p in glob.glob(str(path), recursive=True)
                              if Path(p).is_file()), key=lambda p: p.as_posix())
            if not matches:
                raise FileNotFoundError(str(path))
        for match in matches:
            if match.suffix.lower() not in PARSER_VERSIONS:
                raise ValueError(f"Unsupported document extension: {match.name}")
            resolved = match.resolve()
            if resolved not in seen:
                seen.add(resolved)
                found.append(resolved)
    if not found:
        raise FileNotFoundError("No supported local documents")
    by_name = {}
    for path in found:
        if path.name in by_name:
            raise ValueError(f"Duplicate source filename: {path.name}")
        by_name[path.name] = path
    if config.required_files:
        missing = [name for name in config.required_files if name not in by_name]
        if missing:
            raise FileNotFoundError("Missing required documents: " + ", ".join(missing))
        return [by_name[name] for name in config.required_files]
    return found


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_document_manifest(paths, config: ParserConfig = None):
    return {p.name: {"sha256": sha256_file(p), "size_bytes": p.stat().st_size,
                     "parser_version": PARSER_VERSIONS[p.suffix.lower()]}
            for p in load_sources(paths, config)}
