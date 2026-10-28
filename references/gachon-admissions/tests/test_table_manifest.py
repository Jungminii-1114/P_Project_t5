import hashlib
import re
from pathlib import Path

from tests.source_helpers import load_definitions


REQUIRED = [
    "01_2027학년도_재외국민_모집요강.hwp",
    "02_2027학년도_지역의사선발전형_안내.pdf",
    "03_2027학년도_수시_모집요강.pdf",
    "04_2027학년도_정시_모집요강.pdf",
    "05_2027학년도_수시_면접고사_일정.pdf",
]
PARSER_VERSIONS = {
    ".hwp": "hwp-elements-pyhwp-v1",
    ".pdf": "pymupdf-text-pdfplumber-v1",
}


def _table_functions():
    return load_definitions(
        "def parse_table",
        namespace={
            "re": re,
            "DOC_TITLES": {
                "01": "fictional hwp",
                "02": "fictional pdf",
                "03": "fictional pdf",
                "04": "fictional pdf",
                "05": "fictional pdf",
            },
            "NUMERIC": re.compile(r"^[\d,./~%()~\-–\s]+$"),
            "SYMBOLS": {"O", "■", "□", "△", "○", "●", "X", "▲", "★", "◉"},
            "GENERIC_COLS": {"비고", "계열", "연번", "번호", "구분"},
        },
        definitions_only=True,
    )


def _manifest_functions():
    return load_definitions(
        "def build_document_manifest",
        namespace={
            "Path": Path,
            "hashlib": hashlib,
            "REQUIRED": REQUIRED,
            "PARSER_VERSIONS": PARSER_VERSIONS,
        },
        definitions_only=True,
    )


def test_row_summary_keeps_equal_values_in_distinct_columns():
    ns = _table_functions()
    _, mode, cols, data = ns["parse_table"](
        "| 모집단위 | 일반전형1 | 일반전형2 |\n"
        "| --- | --- | --- |\n"
        "| 가상학과 | 30 | 30 |"
    )

    assert ns["row_summary"](cols, data, mode) == (
        "- 가상학과: 일반전형1=30, 일반전형2=30"
    )


def test_dedup_cells_only_collapses_repeated_non_value_labels():
    dedup_cells = _table_functions()["dedup_cells"]

    assert dedup_cells(["가상학과", "가상학과", "30", "30", ""]) == [
        "가상학과", "30", "30", ""
    ]
    assert dedup_cells(["가상학과", "가상학과", "30", "비고", "비고"]) == [
        "가상학과", "30", "비고", "비고"
    ]


def test_roster_summary_keeps_duplicate_values_after_outer_blank_cells():
    row_summary = _table_functions()["row_summary"]

    assert row_summary(
        ["모집단위", "장학내역", "수업학점", "성적기준"],
        [["", "가상학과", "등록금 전액", "-", "-", ""]],
        "roster",
    ) == "- 가상학과 등록금 전액: 수업학점=-, 성적기준=-"


def test_manifest_hashes_exact_required_inputs_and_ignores_extra_documents(tmp_path):
    payloads = {name: f"fictional input {index}".encode() for index, name in enumerate(REQUIRED)}
    for name, payload in payloads.items():
        (tmp_path / name).write_bytes(payload)
    (tmp_path / "extra.pdf").write_bytes(b"must not be parsed")

    ns = _manifest_functions()
    manifest = ns["build_document_manifest"](tmp_path)

    assert list(manifest) == REQUIRED
    assert "extra.pdf" not in manifest
    for name, payload in payloads.items():
        assert manifest[name]["sha256"] == hashlib.sha256(payload).hexdigest()
        assert manifest[name]["size_bytes"] == len(payload)
        assert manifest[name]["parser_version"] == PARSER_VERSIONS[Path(name).suffix.lower()]


def test_required_files_reports_missing_required_input(tmp_path):
    (tmp_path / REQUIRED[0]).write_bytes(b"present")

    required_files = _manifest_functions()["required_files"]
    try:
        required_files(tmp_path)
    except FileNotFoundError as exc:
        assert all(name in str(exc) for name in REQUIRED[1:])
    else:
        raise AssertionError("missing required input must fail before parsing")


def test_parsing_invokes_parsers_for_required_files_only(tmp_path):
    for name in REQUIRED:
        (tmp_path / name).write_bytes(b"fictional parser fixture")
    (tmp_path / "extra.pdf").write_bytes(b"must not be parsed")
    calls = []

    def fake_hwp(path):
        calls.append(path.name)
        return [f"hwp:{path.name}"]

    def fake_pdf(path):
        calls.append(path.name)
        return [f"pdf:{path.name}"]

    parse_required_files = _manifest_functions()["parse_required_files"]
    results = parse_required_files(tmp_path, fake_hwp, fake_pdf)

    assert calls == REQUIRED
    assert len(results) == len(REQUIRED)
