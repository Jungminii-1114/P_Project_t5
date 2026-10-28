# baseline-1 동결 레퍼런스 — v23(64ac263) build_notebook.py §1에서 이식. 수정 금지. 개선은 새 버전에서.

import hashlib
from pathlib import Path

from .constants import PARSER_VERSIONS, REQUIRED


def required_files(directory: Path):
    """필수 원본 5개만 고정 순서로 반환하고 누락 시 파싱 전에 알린다."""
    directory = Path(directory)
    missing = [name for name in REQUIRED if not (directory / name).is_file()]
    if missing:
        raise FileNotFoundError("필수 문서가 없습니다: " + ", ".join(missing))
    return [directory / name for name in REQUIRED]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_document_manifest(directory: Path):
    """필수 원본별 SHA-256, 크기, 파서 구현 버전을 기록한다."""
    manifest = {}
    for path in required_files(directory):
        suffix = path.suffix.lower()
        if suffix not in PARSER_VERSIONS:
            raise ValueError(f"지원하지 않는 문서 확장자: {path.name}")
        manifest[path.name] = {
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
            "parser_version": PARSER_VERSIONS[suffix],
        }
    return manifest


def load_sources(directory: Path):
    """고정된 순서로 필수 원문 파일 경로를 반환한다."""
    return required_files(directory)


def parse_required_files(directory: Path, parse_hwp, parse_pdf):
    """필수 원본 5개만 해당 파서로 전달한다. 다른 PDF/HWP는 무시한다."""
    parsed = []
    for path in required_files(directory):
        if path.suffix.lower() == ".hwp":
            parsed.extend(parse_hwp(path))
        elif path.suffix.lower() == ".pdf":
            parsed.extend(parse_pdf(path))
    return parsed
