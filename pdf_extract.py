"""PyMuPDF native-text demo. No OCR, VLM, or table-meaning verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf


PROJECT_ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "pymupdf-demo/1"


@dataclass(frozen=True)
class DocumentManifest:
    doc_id: str
    source_url: str | None
    local_file: str
    local_file_dir: str
    version_sha256: str
    page_count: int
    document_title: str
    title_verified_by_human: bool
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PageManifest:
    doc_id: str
    version_sha256: str
    pdf_page: int
    printed_page_label: str | None
    char_count: int
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class TextBlock:
    doc_id: str
    version_sha256: str
    block_id: str
    pdf_page: int
    block_index: int
    kind: str
    text: str
    source_locator: dict[str, Any]
    extraction_method: str = "native_text"
    verification_status: str = "unverified"


@dataclass(frozen=True)
class PdfResult:
    document: DocumentManifest
    pages: list[PageManifest]
    blocks: list[TextBlock]


def file_sha256(pdf_path: Path) -> str:
    """큰 PDF도 한 번에 메모리에 올리지 않고 1 MiB씩 해시를 갱신한다."""
    hasher = hashlib.sha256()
    with pdf_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_manifest(
    pdf_path: Path,
    page_count: int,
    source_url: str | None = None,
    pdf_metadata: dict[str, Any] | None = None,
) -> DocumentManifest:
    """문서 전체 메타데이터만 생성한다. 페이지 순회는 extract_pdf에서 수행한다."""
    sha = file_sha256(pdf_path)
    return DocumentManifest(
        doc_id="doc_" + sha[:16],
        source_url=source_url,
        local_file=str(pdf_path),
        local_file_dir=str(pdf_path.parent),
        version_sha256=sha,
        page_count=page_count,
        document_title=pdf_path.stem,
        title_verified_by_human=False,
        metadata={
            "schema_version": SCHEMA_VERSION,
            "source_name": pdf_path.name,
            "parser": "pymupdf",
            "parser_version": pymupdf.VersionBind,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "pdf_metadata": pdf_metadata or {},
            "extraction_method": "native_text",
            "sort_reading_order": True,
        },
    )


def extract_pdf(
    pdf_path: str | Path,
    source_url: str | None = None,
    low_text_threshold: int = 50,
) -> PdfResult:
    """PDF를 한 번 열고 페이지 텍스트와 출처가 있는 블록을 함께 추출한다."""
    path = Path(pdf_path).expanduser().resolve()
    if low_text_threshold < 0:
        raise ValueError("텍스트 길이 기준은 0 이상이어야 합니다.")
    if not path.is_file():
        raise ValueError(f"PDF 파일을 찾을 수 없습니다: {path}")
    with path.open("rb") as stream:
        if b"%PDF-" not in stream.read(1024):
            raise ValueError(f"PDF 헤더가 없습니다. HTML 저장 여부를 확인하세요: {path.name}")

    with pymupdf.open(path) as document:
        if not document.is_pdf:
            raise ValueError("PDF 형식만 지원합니다.")
        if document.needs_pass:
            raise ValueError(f"암호가 필요한 PDF입니다: {path.name}")
        if document.page_count == 0:
            raise ValueError(f"페이지가 없는 PDF입니다: {path.name}")
        manifest = build_manifest(path, document.page_count, source_url, document.metadata)
        pages: list[PageManifest] = []
        blocks: list[TextBlock] = []

        for index, page in enumerate(document):
            page_number = index + 1  # 파일 페이지는 1부터 시작한다.
            textpage = page.get_textpage(flags=pymupdf.TEXTFLAGS_TEXT)
            text = page.get_text("text", textpage=textpage, sort=True)
            char_count = len(text.strip())
            status = "no_native_text" if not char_count else (
                "low_text" if char_count < low_text_threshold else "native_text_extracted"
            )
            pages.append(PageManifest(
                doc_id=manifest.doc_id,
                version_sha256=manifest.version_sha256,
                pdf_page=page_number,
                printed_page_label=None,  # 인쇄된 쪽번호는 자동 추측하지 않는다.
                char_count=char_count,
                text=text,
                metadata={
                    "schema_version": SCHEMA_VERSION,
                    "extraction_method": "native_text",
                    "extraction_status": status,
                    "verification_status": "unverified",
                    "needs_review": status != "native_text_extracted",
                    "low_text_threshold": low_text_threshold,
                    "pdf_page_label": page.get_label() or None,
                    "width_pt": page.cropbox.width,
                    "height_pt": page.cropbox.height,
                    "coordinate_space": "pymupdf_unrotated_page",
                    "rotation": page.rotation,
                },
            ))
            for block in page.get_text("blocks", textpage=textpage, sort=True):
                x0, y0, x1, y1, block_text, block_index, block_type = block
                if block_type != 0 or not block_text.strip():
                    continue
                blocks.append(TextBlock(
                    doc_id=manifest.doc_id,
                    version_sha256=manifest.version_sha256,
                    block_id=f"{manifest.doc_id}:p{page_number:04d}:b{block_index:04d}",
                    pdf_page=page_number,
                    block_index=block_index,
                    kind="text",
                    text=block_text,
                    source_locator={
                        "type": "pdf_page_bbox",
                        "pdf_page": page_number,
                        "bbox": [x0, y0, x1, y1],
                        "units": "pt",
                        "coordinate_space": "pymupdf_unrotated_page",
                    },
                ))

    return PdfResult(manifest, pages, blocks)


def compact(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def write_jsonl(path: Path, rows: list[Any]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")


def save_result(
    result: PdfResult,
    output_root: str | Path,
    keyword: str | None = None,
    split_pages: bool = False,
) -> Path:
    """원본과 이전 실험 폴더를 보존하고 PDF별 폴더에 결과를 저장한다."""
    manifest = result.document
    name = re.sub(r"[^\w.-]+", "_", Path(manifest.local_file).stem).strip("._") or "document"
    output = Path(output_root).expanduser().resolve() / f"{name}_{manifest.version_sha256[:12]}"
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(asdict(manifest), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_jsonl(output / "pages.jsonl", result.pages)
    write_jsonl(output / "blocks.jsonl", result.blocks)
    full_text = "\n\f\n".join(
        f"[PDF page {page.pdf_page}]\n{page.text}" for page in result.pages
    )
    (output / "output.txt").write_text(full_text, encoding="utf-8")
    matches = [
        page for page in result.pages
        if keyword and compact(keyword) and compact(keyword) in compact(page.text)
    ]
    (output / "candidate_pages.txt").write_text(
        "\n\n".join(f"[PDF page {page.pdf_page}]\n{page.text}" for page in matches),
        encoding="utf-8",
    )

    if split_pages:
        page_output = output / "pages"
        page_output.mkdir(exist_ok=True)
        with pymupdf.open(manifest.local_file) as original:
            for index in range(original.page_count):
                with pymupdf.open() as single:
                    single.insert_pdf(original, from_page=index, to_page=index)
                    single.save(page_output / f"page_{index + 1:04d}.pdf")

    summary = {
        "schema_version": SCHEMA_VERSION,
        "doc_id": manifest.doc_id,
        "version_sha256": manifest.version_sha256,
        "page_count": manifest.page_count,
        "block_count": len(result.blocks),
        "total_char_count": sum(page.char_count for page in result.pages),
        "no_native_text_pages": [page.pdf_page for page in result.pages if not page.char_count],
        "low_text_pages": [
            page.pdf_page for page in result.pages
            if page.char_count and page.metadata["needs_review"]
        ],
        "keyword": keyword,
        "keyword_candidate_pages": [page.pdf_page for page in matches],
        "split_pages": split_pages,
        "output_dir": str(output),
        "limitations": [
            "native_text_only_no_ocr_or_vlm",
            "table_headers_units_and_reading_order_not_verified",
            "printed_page_labels_not_verified",
        ],
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output


def project_path(path: Path) -> Path:
    path = path.expanduser()
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="로컬 PDF 텍스트·블록·출처 추출 데모")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--pdf", type=Path, help="PDF 한 개")
    inputs.add_argument("--file-dir", type=Path, help="PDF 폴더 (기본: 프로젝트의 data/raw)")
    parser.add_argument("--source-url", help="출처 URL. 생략하면 null, 배치에서는 모든 문서에 공통 기록")
    parser.add_argument("--out", type=Path, default=Path("data/processed/pymupdf_demo"), help="결과 루트 폴더")
    parser.add_argument("--keyword", help="후보 페이지를 찾을 키워드. 검색 또는 의미 검증 기능은 아님")
    parser.add_argument("--low-text-threshold", type=int, default=50, help="검토할 저텍스트 페이지 기준")
    parser.add_argument("--split-pages", action="store_true", help="페이지별 PDF도 추가 저장")
    args = parser.parse_args(argv)
    if args.low_text_threshold < 0:
        parser.error("--low-text-threshold는 0 이상이어야 합니다.")
    if args.pdf:
        paths = [project_path(args.pdf)]
    else:
        directory = project_path(args.file_dir or Path("data/raw"))
        if not directory.is_dir():
            parser.error(f"입력 폴더를 찾을 수 없습니다: {directory}")
        paths = sorted(
            (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
            key=lambda path: path.name,
        )
        if not paths:
            parser.error(f"입력 폴더에 PDF가 없습니다: {directory}")

    report: dict[str, Any] = {"documents": [], "errors": []}
    for path in paths:
        try:
            result = extract_pdf(path, args.source_url, args.low_text_threshold)
            output = save_result(result, project_path(args.out), args.keyword, args.split_pages)
            report["documents"].append(json.loads((output / "summary.json").read_text(encoding="utf-8")))
        except (OSError, RuntimeError, ValueError) as error:
            report["errors"].append({"file": str(path), "error": str(error)})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
