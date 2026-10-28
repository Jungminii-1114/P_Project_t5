from scripts.diagnose_bm25 import (
    document_extensions,
    parse_src_references,
    score_page_hits,
)


PROFILE_FILES = (
    "01_admissions.hwp",
    "03_regular.pdf",
    "04_early.pdf",
)
EXTENSIONS = document_extensions(PROFILE_FILES)


def test_parse_src_inherits_document_and_switches_after_slash():
    parsed = parse_src_references("03 p.34, p.35 / 04 p.44 / p.46", EXTENSIONS)

    assert parsed["source_status"] == "pdf"
    assert parsed["pdf_pages"] == [
        {"document": "03", "page": 34},
        {"document": "03", "page": 35},
        {"document": "04", "page": 44},
        {"document": "04", "page": 46},
    ]
    assert parsed["hwp_source_segments"] == 0
    assert parsed["unparsed_segments"] == 0


def test_parse_src_expands_pdf_ranges_and_excludes_hwp_sources():
    parsed = parse_src_references("03 p.8-10 / 01 p.5-6 / 01 (전형료 표)", EXTENSIONS)

    assert parsed["pdf_pages"] == [
        {"document": "03", "page": 8},
        {"document": "03", "page": 9},
        {"document": "03", "page": 10},
    ]
    assert parsed["hwp_source_segments"] == 2
    assert parsed["hwp_page_references"] == 2
    assert parsed["source_status"] == "pdf"


def test_parse_src_reports_absent_and_hwp_only_separately():
    absent = parse_src_references(None, EXTENSIONS)
    hwp_only = parse_src_references("01 (전형료 표)", EXTENSIONS)

    assert absent["source_status"] == "absent"
    assert absent["pdf_pages"] == []
    assert hwp_only["source_status"] == "hwp_only"
    assert hwp_only["hwp_source_segments"] == 1
    assert hwp_only["pdf_pages"] == []


def test_page_hit_summary_distinguishes_any_page_from_all_pages():
    targets = [
        {"document": "03", "page": 85},
        {"document": "03", "page": 86},
    ]
    ranked = [
        {"document": "04", "page": 10},
        {"document": "03", "page": 85},
        {"document": "03", "page": 86},
    ]

    top_two = score_page_hits(targets, ranked, top_k=2)
    top_three = score_page_hits(targets, ranked, top_k=3)

    assert top_two["any_page_hit"] is True
    assert top_two["all_pages_hit"] is False
    assert top_two["page_hit_count"] == 1
    assert top_two["target_page_count"] == 2
    assert top_three["all_pages_hit"] is True
    assert top_three["page_hits"] == [
        {"document": "03", "page": 85, "hit": True},
        {"document": "03", "page": 86, "hit": True},
    ]
