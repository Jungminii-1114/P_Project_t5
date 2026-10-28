import os
import re
from concurrent.futures import ThreadPoolExecutor, wait
from types import SimpleNamespace

import pytest

from tests.source_helpers import load_definitions
from tests.test_grounding_prompts import doc


class Clock:
    now = 0.0

    def perf_counter(self):
        return self.now


class Future:
    def __init__(self, clock, delay, result):
        self.clock, self.delay, self.value = clock, delay, result
        self.cancelled = False

    def result(self, timeout=None):
        spent = self.delay if timeout is None else min(self.delay, max(0, timeout))
        self.clock.now += spent
        if spent < self.delay:
            raise TimeoutError()
        return self.value() if callable(self.value) else self.value

    def cancel(self):
        self.cancelled = True


class Pool:
    def __init__(self, clock, delay, result):
        self.clock, self.delay, self.value = clock, delay, result
        self.futures = []

    def submit(self, *args, **kwargs):
        future = Future(self.clock, self.delay, self.value)
        self.futures.append(future)
        return future


def ask_ns():
    clock = Clock()
    ns = load_definitions("def retrieve(query", "DRAFT_PROMPT =", "CITE_RE =",
                          namespace={"re": re, "os": os, "time": clock,
                                     "ThreadPoolExecutor": ThreadPoolExecutor, "wait": wait})
    ns.update(route_query=lambda q: "general", target_doc=lambda q: None,
              search_keywords=lambda q: "경영학과", sub_queries=lambda q: [],
              missing_list_items=lambda *args: [], missing_conditions=lambda *args: [],
              missing_neighbor_details=lambda *args: [])
    return ns, clock


def test_initial_search_is_bounded_by_shared_deadline():
    ns, clock = ask_ns()
    pool = Pool(clock, 50, ([], "general"))
    ns["_search_pool"] = pool
    result = ns["ask"]("가상 질문", return_meta=True)
    assert result["sec"] < 19
    assert "timeout" in result["action"]
    assert pool.futures[0].cancelled


@pytest.mark.parametrize("draft_seconds", [9.1, 16.0])
def test_research_does_not_start_after_nine_seconds(draft_seconds):
    ns, clock = ask_ns()
    evidence = [doc("가상 정보")]
    ns["retrieve"] = lambda *a, **kw: (evidence, "general")
    def llm(*a, **kw):
        clock.now += draft_seconds
        return "제공된 문서에서 확인할 수 없습니다"
    ns["_call_llm"] = llm
    ns["retrieve_more"] = lambda *a, **kw: pytest.fail("late additional search started")
    result = ns["ask"]("가상 질문", return_meta=True)
    assert result["action"] == "research_skipped"
    assert result["sec"] < 19


def test_repair_timeout_keeps_draft_and_logs_pair_repair():
    ns, clock = ask_ns()
    evidence = [doc("경영학과 30명\n간호학과 15명")]
    draft = "경영학과 15명 (출처: 03_2027학년도_수시_모집요강.pdf p.104)"
    ns["retrieve"] = lambda *a, **kw: (evidence, "general")
    calls = []
    def call(system, human, deadline):
        calls.append(system)
        if len(calls) == 1:
            clock.now += 1
            return draft
        clock.now = deadline
        raise TimeoutError()
    ns["_call_llm"] = call
    result = ns["ask"]("가상 질문", return_meta=True)
    assert result["answer"] == draft
    assert result["action"] == "repair_timeout"
    assert result["ground"]["pair_ok"] == 0
    assert len(calls) == 2
    assert result["sec"] < 19


def test_llm_never_starts_with_expired_deadline():
    ns, clock = ask_ns()
    clock.now = 20
    ns["llm"] = SimpleNamespace(invoke=lambda *a, **kw: pytest.fail("expired LLM started"))
    with pytest.raises(TimeoutError):
        ns["_call_llm"]("s", "h", deadline=18)


def test_decomposition_uses_completed_results_without_waiting_for_straggler():
    ns, clock = ask_ns()
    evidence = [doc("가상 기본 근거")]
    extra = doc("가상 추가 근거")
    pool = Pool(clock, 100, ([extra], "general"))
    ns["_search_pool"] = pool
    ns["sub_queries"] = lambda q: ["가상 빠른 질의", "가상 느린 질의"]
    def fake_wait(futures, timeout):
        assert timeout <= 18
        clock.now += timeout
        futures[0].delay = 0
        return {futures[0]}, {futures[1]}
    ns["wait"] = fake_wait
    docs, n_sub = ns["retrieve_multi"]("가상 질문", evidence, deadline=18)
    assert docs == [*evidence, extra]
    assert n_sub == 2
    assert pool.futures[1].cancelled
    assert clock.now < 19


def test_slow_additional_search_retains_partial_draft():
    ns, clock = ask_ns()
    evidence = [doc("가상 기본 근거")]
    ns["retrieve"] = lambda *a, **kw: (evidence, "general")
    def draft(*a, **kw):
        clock.now += 8
        return "일부 정보는 제공된 문서에서 확인할 수 없습니다"
    ns["_call_llm"] = draft
    def slow_more(*a, deadline, **kw):
        return ns["deadline_result"](Future(clock, 50, (evidence, 0)), deadline)
    ns["retrieve_more"] = slow_more
    result = ns["ask"]("가상 질문", return_meta=True)
    assert result["action"] == "research_timeout"
    assert result["answer"] != ns["FALLBACK"]
    assert result["sec"] < 19
