import json
import time
from types import ModuleType
from types import SimpleNamespace

from scripts.run_eval import (
    JUDGE,
    Verdict,
    _meta_evidence,
    evaluate_items,
    instrument_pipeline,
    load_dataset,
    make_judge,
    summarize_results,
    time_score,
)


def test_judge_contract_is_the_v22_contract():
    assert JUDGE == (
        "정답과 예측 답변을 비교하세요. 표현이 달라도 핵심 정보(수치·날짜·대상·조건)가 모두 일치하면 정답입니다.\n"
        "부분점수는 없습니다. 하나라도 빠지거나 틀리면 오답입니다."
    )
    assert list(Verdict.model_fields) == ["correct", "reason"]
    assert Verdict.model_fields["correct"].annotation is bool
    assert Verdict.model_fields["correct"].description == "예측 답변이 정답의 핵심 정보(수치·날짜·대상·조건)를 모두 포함하면 True"
    assert Verdict.model_fields["reason"].default == ""
    assert Verdict.model_fields["reason"].description == "판정 이유"


def test_judge_formats_the_exact_prompt_and_input():
    calls = []

    class Structured:
        def invoke(self, messages):
            calls.append(messages)
            return Verdict(correct=True, reason="ok")

    class FakeLLM:
        def with_structured_output(self, schema):
            assert schema is Verdict
            return Structured()

    judge = make_judge(SimpleNamespace(llm=FakeLLM()))
    judge("질문 원문", "정답 원문", "예측 전문")

    assert calls == [[
        ("system", JUDGE),
        ("human", "[질문]\n질문 원문\n\n[정답]\n정답 원문\n\n[예측]\n예측 전문"),
    ]]


def test_sample3_loader_uses_official_question_and_sample_answer(tmp_path):
    sample_path = tmp_path / "sample.json"
    sample_path.write_text(
        json.dumps([
            {"question": "공식 질문", "sample answer": "공식 정답"},
            {"question": "둘째 질문", "sample answer": "둘째 정답"},
        ], ensure_ascii=False),
        encoding="utf-8",
    )

    assert load_dataset("sample3", sample_path=sample_path) == [
        {"id": 1, "question": "공식 질문", "gold": "공식 정답"},
        {"id": 2, "question": "둘째 질문", "gold": "둘째 정답"},
    ]


def test_evaluate_items_logs_failures_and_continues():
    calls = 0

    def ask(question, return_meta=False):
        nonlocal calls
        calls += 1
        if question == "두 번째 질문":
            raise TimeoutError("do not persist raw exception messages")
        return {
            "answer": "첫 답변 전문",
            "sec": 4.5,
            "route": "table",
            "action": "repair",
            "sub_queries": 2,
            "heuristic_score": 0.61,
            "timings": {"search": 0.8, "draft": 2.4, "repair": 1.0},
            "evidence": [
                {"source": "03_full.pdf", "page": 12, "kind": "table", "chunk": "x" * 250},
            ],
        }

    def judge(question, gold, prediction):
        assert (question, gold, prediction) == ("첫 질문", "기대", "첫 답변 전문")
        return SimpleNamespace(correct=True, reason="핵심 정보 일치")

    rows = evaluate_items(
        [
            {"id": 1, "question": "첫 질문", "gold": "기대"},
            {"id": 2, "question": "두 번째 질문", "gold": "기대2"},
        ],
        "hard20",
        ask,
        judge,
    )

    assert calls == 2
    assert len(rows) == 2
    assert rows[0]["prediction"] == "첫 답변 전문"
    assert rows[0]["ok"] is True
    assert rows[0]["reason"] == "핵심 정보 일치"
    assert rows[0]["timings"] == {"search": 0.8, "draft": 2.4, "repair": 1.0}
    assert rows[0]["evidence"][0]["source"] == "03_full.pdf"
    assert len(rows[0]["evidence"][0]["chunk"]) == 200
    assert rows[0]["heuristic_score"] == 0.61
    assert rows[1]["ok"] is False
    assert rows[1]["prediction"] == ""
    assert "TimeoutError" in rows[1]["reason"]
    assert "do not persist" not in rows[1]["reason"]


def test_summary_includes_latency_buckets_and_correct_only_time_score():
    rows = [
        {"set": "hard20", "ok": True, "sec": 5.0, "time_score": 0.4},
        {"set": "hard20", "ok": True, "sec": 7.5, "time_score": 0.2},
        {"set": "hard20", "ok": False, "sec": 20.0, "time_score": 0.0},
    ]

    summary = summarize_results(rows)["hard20"]

    assert summary["accuracy"] == 2 / 3
    assert summary["correct"] == 2
    assert summary["total"] == 3
    assert summary["mean_sec"] == 10.833333
    assert summary["max_sec"] == 20.0
    assert summary["over_5s"] == 2
    assert summary["over_10s"] == 1
    assert summary["over_19s"] == 1
    assert summary["time_score"] == 0.6


def test_latency_score_is_zero_for_wrong_or_ten_second_answers():
    assert time_score(True, 5.0) == 0.4
    assert time_score(True, 7.5) == 0.2
    assert time_score(True, 10.0) == 0.0
    assert time_score(False, 1.0) == 0.0


def test_v22_instrumentation_records_stages_and_full_source_evidence():
    doc = SimpleNamespace(
        metadata={"source": "03_full_source.pdf", "page": 12, "kind": "table", "raw": "raw"},
        page_content="표 청크 본문",
    )
    module = ModuleType("fake_v22")
    module.DRAFT_PROMPT = "draft"
    module.REPAIR_PROMPT = "repair"

    def retrieve(query):
        time.sleep(0.002)
        return [doc], "general"

    def retrieve_multi(question, docs):
        time.sleep(0.002)
        module.retrieve("nested sub-query")
        return docs, 1

    def retrieve_more(question, docs):
        module.retrieve("extra lookup")
        return docs, 0

    def toc_lookup(question, target):
        return {"source": "03_full_source.pdf", "page": "34", "doc_page": 12, "doc": doc}

    def call_llm(system, human, timeout):
        time.sleep(0.002)
        return "answer"

    module.retrieve = retrieve
    module.retrieve_multi = retrieve_multi
    module.retrieve_more = retrieve_more
    module.toc_lookup = toc_lookup
    module._call_llm = call_llm
    trace_manager = instrument_pipeline(module)
    trace_manager.begin()
    docs, _ = module.retrieve("initial")
    module.retrieve_multi("compound", docs)
    module.retrieve_more("extra", docs)
    module.toc_lookup("page query", "03")
    module._call_llm(module.DRAFT_PROMPT, "", 1)
    module._call_llm(module.REPAIR_PROMPT, "", 1)
    trace = trace_manager.finish()

    assert trace.timings["search"] > 0
    assert trace.timings["draft"] > 0
    assert trace.timings["repair"] > 0
    assert trace.evidence == [{
        "source": "03_full_source.pdf",
        "page": 12,
        "kind": "table",
        "chunk": "표 청크 본문",
    }]
    assert _meta_evidence({"docs": [("03", 12)]}, trace) == trace.evidence
