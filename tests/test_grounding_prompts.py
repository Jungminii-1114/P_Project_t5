import re
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from tests.source_helpers import load_definitions


def verifier():
    return load_definitions("CITE_RE =", namespace={"re": re})


def doc(raw, source="03_2027학년도_수시_모집요강.pdf", page=104):
    return SimpleNamespace(page_content=raw, metadata={"raw": raw, "source": source, "page": page, "kind": "text"})


def test_cross_entity_value_is_not_grounded():
    ns = verifier()
    g = ns["ground_answer"]("경영학과 15명 (출처: 03_2027학년도_수시_모집요강.pdf p.104)",
                            [doc("경영학과 30명\n간호학과 15명")])
    assert g["score"] < 0.78
    assert g["pair_ok"] == 0


def test_citation_requires_entire_normalized_filename():
    ns = verifier()
    g = ns["ground_answer"]("경영학과 30명 (출처: 03_없는파일.pdf p.104)", [doc("경영학과 30명")])
    assert g["cite_ok"] == 0


def test_pairs_stay_within_one_sentence_or_table_row():
    ns = verifier()
    for raw in ["경영학과 30명. 간호학과 15명.", "| 경영학과 | 30 |\n| 간호학과 | 15 |"]:
        assert ns["ground_answer"]("경영학과 15명", [doc(raw)])["pair_ok"] == 0
    assert ns["ground_answer"]("경영학과 30명", [doc("| 경영학과 | 30명 |")])["pair_ok"] == 1


def test_partial_answer_prompts_allow_abstention():
    ns = load_definitions("DRAFT_PROMPT =", namespace={"os": __import__("os"), "ThreadPoolExecutor": ThreadPoolExecutor})
    assert "NEVER say a rule" not in ns["DRAFT_PROMPT"]
    assert "The evidence DOES contain" not in ns["REPAIR_PROMPT"]
    for prompt in [ns["DRAFT_PROMPT"], ns["REPAIR_PROMPT"]]:
        assert "제공된 문서에서 확인할 수 없습니다" in prompt


def test_homepage_synonym_contains_only_generic_terms():
    ns = load_definitions("SYNONYMS =", namespace={"re": re})
    assert ns["SYNONYMS"]["홈페이지"] == "www 누리집"
