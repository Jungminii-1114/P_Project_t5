"""Compare saved v22/v23 evaluation runs without calling the model or pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_eval import ROOT, summarize_results, time_score


SEOUL = timezone(timedelta(hours=9), name="Asia/Seoul")
EXPECTED_SETS = ("sample3", "hard20", "holdout10", "drive20")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _normalise_row(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    try:
        seconds = max(0.0, float(result.get("sec", 0.0) or 0.0))
    except (TypeError, ValueError):
        seconds = 0.0
    result["sec"] = seconds
    result["ok"] = bool(result.get("ok", False))
    if "time_score" not in result or result["time_score"] is None:
        result["time_score"] = time_score(result["ok"], seconds)
    try:
        result["time_score"] = float(result["time_score"])
    except (TypeError, ValueError):
        result["time_score"] = time_score(result["ok"], seconds)
    result.setdefault("question", result.get("q", ""))
    result.setdefault("prediction", result.get("pred", ""))
    result.setdefault("reason", "")
    result.setdefault("evidence", [])
    result.setdefault("events", [])
    return result


def load_run(run_dir: str | Path) -> dict[str, Any]:
    """Load one completed or in-progress run using only its saved files."""
    path = Path(run_dir).expanduser().resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"평가 실행 폴더가 없습니다: {path}")
    results_path = path / "results.jsonl"
    if not results_path.is_file():
        raise FileNotFoundError(f"문항 로그가 없습니다: {results_path}")
    rows = []
    with results_path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{results_path.name}:{line_number} JSON 오류: {exc.msg}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{results_path.name}:{line_number} 문항 로그는 JSON object여야 합니다.")
            rows.append(_normalise_row(row))

    saved_summary_path = path / "summary.json"
    saved_summary = _read_json(saved_summary_path) if saved_summary_path.is_file() else None
    computed_summary = summarize_results(rows)
    return {
        "path": str(path),
        "rows": rows,
        "summaries": computed_summary,
        "summary_source": "results.jsonl",
        "saved_summary": saved_summary,
        "complete_summary_file": saved_summary_path.is_file(),
    }


def _summary_for(run: dict[str, Any], set_name: str) -> dict[str, Any] | None:
    summaries = run.get("summaries")
    if not isinstance(summaries, dict):
        summaries = summarize_results(run.get("rows", []))
    value = summaries.get(set_name)
    if value is None:
        return None
    return dict(value)


def _row_key(row: dict[str, Any]) -> tuple[str, str]:
    set_name = str(row.get("set", "unknown"))
    item_id = row.get("id")
    if item_id is not None:
        return set_name, f"id:{item_id}"
    question = " ".join(str(row.get("question", "")).split()).casefold()
    return set_name, f"question:{question}"


def _match_rows(
    old_rows: Iterable[dict[str, Any]], new_rows: Iterable[dict[str, Any]], set_name: str
) -> list[tuple[dict[str, Any] | None, dict[str, Any] | None]]:
    old = [row for row in old_rows if str(row.get("set")) == set_name]
    new = [row for row in new_rows if str(row.get("set")) == set_name]
    new_by_key = {_row_key(row): row for row in new}
    old_keys = set()
    pairs = []
    for row in old:
        key = _row_key(row)
        pairs.append((row, new_by_key.get(key)))
        old_keys.add(key)
    pairs.extend((None, row) for row in new if _row_key(row) not in old_keys)
    return pairs


def _evidence_signature(row: dict[str, Any] | None) -> list[tuple[str, str, str, str]]:
    if row is None:
        return []
    signature = []
    evidence = row.get("evidence", [])
    if not isinstance(evidence, list):
        return []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        signature.append((
            str(item.get("source", "")),
            str(item.get("page", "")),
            str(item.get("kind", "")),
            str(item.get("chunk", ""))[:200],
        ))
    return signature


def _changed_fields(old: dict[str, Any] | None, new: dict[str, Any] | None) -> list[str]:
    if old is None or new is None:
        return ["row_missing"]
    fields = []
    for field in ("ok", "prediction", "reason"):
        if old.get(field) != new.get(field):
            fields.append(field)
    if old.get("ground") != new.get("ground"):
        fields.append("ground")
    if _evidence_signature(old) != _evidence_signature(new):
        fields.append("evidence")
    return fields


def _status(old: dict[str, Any] | None, new: dict[str, Any] | None) -> str:
    if old is None:
        return "only_v23"
    if new is None:
        return "only_v22"
    old_ok, new_ok = bool(old.get("ok")), bool(new.get("ok"))
    if old_ok and not new_ok:
        return "regression"
    if not old_ok and new_ok:
        return "improvement"
    changed_prediction = old.get("prediction") != new.get("prediction")
    if old_ok and new_ok:
        return "changed_both_correct" if changed_prediction else "unchanged_correct"
    return "changed_both_wrong" if changed_prediction else "unchanged_wrong"


def _evidence_refs(row: dict[str, Any] | None) -> list[str]:
    if row is None or not isinstance(row.get("evidence"), list):
        return []
    refs = []
    for item in row["evidence"]:
        if not isinstance(item, dict):
            continue
        source = item.get("source", "")
        page = item.get("page", "?")
        kind = item.get("kind", "")
        ref = f"{source} p.{page}" + (f" ({kind})" if kind else "")
        if ref not in refs:
            refs.append(ref)
    return refs


def _ground_digest(row: dict[str, Any] | None) -> dict[str, Any] | None:
    ground = row.get("ground") if row else None
    if not isinstance(ground, dict):
        return None
    keys = ("score", "num_ok", "date_ok", "ent_ok", "cite_ok", "pair_ok", "not_found", "unsupported_pairs")
    return {key: ground[key] for key in keys if key in ground}


def _verdict_text(row: dict[str, Any] | None, version: str) -> str:
    if row is None:
        return f"{version} 로그에 이 문항이 없습니다."
    return f"{version} 판정 이유: {row.get('reason') or '기록 없음'}"


def _explanation(old: dict[str, Any] | None, new: dict[str, Any] | None, status: str) -> str:
    if old is None or new is None:
        return "비교 대상 중 한 버전의 저장 로그에 문항이 없어 판정 변화는 확인할 수 없습니다. " + _verdict_text(old, "v22") + " " + _verdict_text(new, "v23")

    lead = {
        "regression": "판정이 v22 정답에서 v23 오답으로 바뀌었습니다.",
        "improvement": "판정이 v22 오답에서 v23 정답으로 바뀌었습니다.",
        "changed_both_correct": "두 버전 모두 정답 판정이지만 예측 답변이 달라졌습니다.",
        "unchanged_correct": "두 버전 모두 정답 판정이며 예측 답변이 같습니다.",
        "changed_both_wrong": "두 버전 모두 오답 판정이고 예측 답변이 달라졌습니다.",
        "unchanged_wrong": "두 버전 모두 오답 판정이며 예측 답변이 같습니다.",
    }.get(status, "두 저장 로그의 결과를 비교했습니다.")
    parts = [lead, _verdict_text(old, "v22"), _verdict_text(new, "v23")]

    old_ground, new_ground = _ground_digest(old), _ground_digest(new)
    if old_ground != new_ground and (old_ground is not None or new_ground is not None):
        parts.append(f"저장된 ground 기록: v22={old_ground!r}; v23={new_ground!r}.")
    old_refs, new_refs = _evidence_refs(old), _evidence_refs(new)
    if old_refs != new_refs:
        parts.append(f"저장된 근거 참조: v22={old_refs or ['없음']}; v23={new_refs or ['없음']}.")
    elif new_refs:
        parts.append(f"저장된 근거 참조: {new_refs}.")
    if old.get("prediction") != new.get("prediction"):
        parts.append(f"저장된 예측: v22={old.get('prediction') or '빈 답변'}; v23={new.get('prediction') or '빈 답변'}.")
    return " ".join(parts)


def _comparison_item(old: dict[str, Any] | None, new: dict[str, Any] | None) -> dict[str, Any]:
    ref = old or new or {}
    status = _status(old, new)
    fields = _changed_fields(old, new)
    return {
        "id": ref.get("id"),
        "question": ref.get("question", ""),
        "gold": ref.get("gold", ""),
        "status": status,
        "changed_fields": fields,
        "explanation": _explanation(old, new, status),
        "v22": _row_details(old),
        "v23": _row_details(new),
    }


def _row_details(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "ok": bool(row.get("ok")),
        "prediction": row.get("prediction", ""),
        "reason": row.get("reason", ""),
        "sec": row.get("sec"),
        "time_score": row.get("time_score"),
        "route": row.get("route"),
        "action": row.get("action"),
        "heuristic_score": row.get("heuristic_score"),
        "ground": row.get("ground"),
        "events": row.get("events", []),
        "evidence": row.get("evidence", []),
    }


def _regressions(v22: dict[str, Any], v23: dict[str, Any], set_name: str) -> list[dict[str, Any]]:
    result = []
    for old, new in _match_rows(v22["rows"], v23["rows"], set_name):
        if old is not None and new is not None and bool(old.get("ok")) and not bool(new.get("ok")):
            result.append(_comparison_item(old, new))
    return result


def _sample_repeat(run: dict[str, Any], index: int) -> dict[str, Any]:
    summary = _summary_for(run, "sample3")
    rows = [row for row in run.get("rows", []) if str(row.get("set")) == "sample3"]
    return {
        "repeat": index,
        "run_dir": run.get("path"),
        "summary": summary,
        "results": [
            {
                "id": row.get("id"),
                "question": row.get("question", ""),
                "ok": bool(row.get("ok")),
                "reason": row.get("reason", ""),
                "sec": row.get("sec"),
                "time_score": row.get("time_score"),
                "prediction": row.get("prediction", ""),
            }
            for row in rows
        ],
        "is_3_of_3": bool(summary and summary.get("correct") == 3 and summary.get("total") == 3),
    }


def _latency_check(v23: dict[str, Any], sample_runs: list[dict[str, Any]]) -> dict[str, Any]:
    records = [("v23", row) for row in v23.get("rows", [])]
    for index, run in enumerate(sample_runs, start=1):
        records.extend((f"sample repeat {index}", row) for row in run.get("rows", []) if str(row.get("set")) == "sample3")
    violations = [
        {"source": source, "set": row.get("set"), "id": row.get("id"), "sec": row.get("sec")}
        for source, row in records if float(row.get("sec", 0.0)) >= 19.0
    ]
    times = [float(row.get("sec", 0.0)) for _, row in records]
    return {
        "passed": bool(records) and not violations,
        "criterion": "Every v23 response, including the three sample3 repeat runs, is under 19 seconds.",
        "response_count": len(records),
        "max_sec": max(times, default=None),
        "violations": violations,
    }


def build_comparison(
    v22: dict[str, Any],
    v23: dict[str, Any],
    sample_runs: list[dict[str, Any]],
    clean: dict[str, Any],
    *,
    generated_at: str | None = None,
    f2_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble summaries, acceptance checks, and explanations from saved outputs only."""
    per_set = {}
    all_set_names = list(EXPECTED_SETS)
    all_set_names.extend(
        name
        for run in (v22, v23)
        for name in (run.get("summaries") or summarize_results(run.get("rows", [])))
        if name not in all_set_names
    )
    for set_name in all_set_names:
        old_summary = _summary_for(v22, set_name)
        new_summary = _summary_for(v23, set_name)
        if old_summary is None and new_summary is None:
            continue
        per_set[set_name] = {
            "v22": old_summary,
            "v23": new_summary,
            "delta": {
                "correct": (new_summary or {}).get("correct", 0) - (old_summary or {}).get("correct", 0),
                "accuracy": round((new_summary or {}).get("accuracy", 0.0) - (old_summary or {}).get("accuracy", 0.0), 6),
                "time_score": round((new_summary or {}).get("time_score", 0.0) - (old_summary or {}).get("time_score", 0.0), 6),
            },
        }

    sample_repeat_results = [_sample_repeat(run, index) for index, run in enumerate(sample_runs, start=1)]
    hard_regressions = _regressions(v22, v23, "hard20")
    holdout_regressions = _regressions(v22, v23, "holdout10")
    drive_pairs = _match_rows(v22.get("rows", []), v23.get("rows", []), "drive20")
    drive_outcomes = [_comparison_item(old, new) for old, new in drive_pairs]
    drive_v22_count = sum(1 for row in v22.get("rows", []) if str(row.get("set")) == "drive20")
    drive_v23_count = sum(1 for row in v23.get("rows", []) if str(row.get("set")) == "drive20")

    sample_ok = len(sample_runs) == 3 and all(item["is_3_of_3"] for item in sample_repeat_results)
    sample_expected = [
        {"repeat": item["repeat"], "correct": (item.get("summary") or {}).get("correct"),
         "total": (item.get("summary") or {}).get("total"), "passed": item["is_3_of_3"]}
        for item in sample_repeat_results
    ]
    latency = _latency_check(v23, sample_runs)
    def set_count(run: dict[str, Any], name: str) -> int:
        return sum(1 for row in run.get("rows", []) if str(row.get("set")) == name)

    hard_present = (
        set_count(v22, "hard20") == 20 and set_count(v23, "hard20") == 20
    )
    holdout_present = (
        set_count(v22, "holdout10") == 10 and set_count(v23, "holdout10") == 10
    )
    expected_main_counts = {"sample3": 3, "hard20": 20, "holdout10": 10, "drive20": 20}
    v23_counts = {name: set_count(v23, name) for name in expected_main_counts}
    sample_counts = [set_count(run, "sample3") for run in sample_runs]
    sample_dirs = [str(run.get("path", "")) for run in sample_runs]
    sample_dirs_unique = len(set(sample_dirs)) == 3 and all(sample_dirs)
    clean_failed = clean.get("failed_cell_count")
    clean_cells = clean.get("code_cell_count")
    clean_passed = clean_failed == 0 and isinstance(clean_cells, int) and clean_cells > 0
    repair_events = [
        event
        for row in v23.get("rows", [])
        for event in (row.get("events") if isinstance(row.get("events"), list) else [])
        if isinstance(event, dict) and event.get("stage") == "repair"
    ]
    reproduction_events = [event for event in (f2_trace or {}).get("events", [])
                           if event.get("stage") == "repair" and event.get("unsupported_pairs")]
    f2_observed = bool(reproduction_events) and (f2_trace or {}).get("action") == "repair"

    return {
        "generated_at": generated_at or datetime.now(SEOUL).isoformat(timespec="seconds"),
        "timezone": "Asia/Seoul",
        "inputs": {
            "v22_run_dir": v22.get("path"),
            "v23_run_dir": v23.get("path"),
            "sample_run_dirs": [run.get("path") for run in sample_runs],
            "clean_json": clean.get("_path"),
        },
        "per_set": per_set,
        "sample_repeat_results": sample_repeat_results,
        "acceptance_checks": {
            "sample3_all_repeats_3_of_3": {
                "passed": sample_ok,
                "required_repeat_count": 3,
                "observed_repeat_count": len(sample_runs),
                "details": sample_expected,
            },
            "all_v23_responses_under_19s": latency,
            "v23_run_contains_expected_sets": {
                "passed": v23_counts == expected_main_counts,
                "expected_counts": expected_main_counts,
                "observed_counts": v23_counts,
            },
            "sample_repeat_runs_are_distinct_and_complete": {
                "passed": len(sample_runs) == 3 and sample_dirs_unique and sample_counts == [3, 3, 3],
                "distinct_run_dirs": sample_dirs_unique,
                "observed_sample3_counts": sample_counts,
            },
            "hard20_accuracy_drop_at_most_2": {
                "passed": hard_present and per_set["hard20"]["delta"]["correct"] >= -2,
                "correct_count_drop": -per_set.get("hard20", {}).get("delta", {}).get("correct", 0),
                "observed_regressions": len(hard_regressions),
                "maximum_allowed": 2,
                "data_present": hard_present,
            },
            "holdout10_accuracy_drop_at_most_2": {
                "passed": holdout_present and per_set["holdout10"]["delta"]["correct"] >= -2,
                "correct_count_drop": -per_set.get("holdout10", {}).get("delta", {}).get("correct", 0),
                "observed_regressions": len(holdout_regressions),
                "maximum_allowed": 2,
                "data_present": holdout_present,
            },
            "drive20_comparison_complete": {
                "passed": drive_v22_count == 20 and drive_v23_count == 20 and sum(pair[0] is not None and pair[1] is not None for pair in drive_pairs) == 20,
                "v22_count": drive_v22_count,
                "v23_count": drive_v23_count,
                "matched_count": sum(pair[0] is not None and pair[1] is not None for pair in drive_pairs),
                "expected_count": 20,
            },
            "clean_notebook_execution": {
                "passed": clean_passed,
                "code_cell_count": clean_cells,
                "failed_cell_count": clean_failed,
                "total_cell_wall_seconds": clean.get("total_cell_wall_seconds"),
                "notebook": clean.get("notebook"),
            },
            "f2_reproduction_repair_observed": {
                "passed": f2_observed if f2_trace is not None else None,
                "status": "observed_in_api_free_reproduction" if f2_observed else "not_checkable_from_selected_run_logs",
                "repair_event_count": len(repair_events),
                "reproduction_events": reproduction_events,
                "note": "별도 API-free F2 재현 trace의 잘못된 개체·숫자 연결에 대한 교정 이벤트를 검사합니다.",
            },
        },
        "regressions": {"hard20": hard_regressions, "holdout10": holdout_regressions},
        "drive20": {
            "v22_count": drive_v22_count,
            "v23_count": drive_v23_count,
            "matched_count": sum(pair[0] is not None and pair[1] is not None for pair in drive_pairs),
            "outcomes": drive_outcomes,
        },
        "clean_run": {
            key: clean.get(key)
            for key in ("notebook", "started_at", "finished_at", "python_version", "code_cell_count", "failed_cell_count", "total_cell_wall_seconds")
            if key in clean
        },
        "analysis_basis": "문항 비교 설명은 저장된 prediction, reason, ground, evidence, events에서만 구성했습니다. 로그에 없는 원인은 추정하지 않았습니다.",
    }


def _md(value: Any, limit: int | None = None) -> str:
    text = str(value if value is not None else "—")
    if limit is not None and len(text) > limit:
        text = text[:limit - 1] + "…"
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("\r\n", "<br>").replace("\n", "<br>")


def _fmt_summary(summary: dict[str, Any] | None) -> str:
    if summary is None:
        return "자료 없음"
    return (
        f"{summary.get('correct', 0)}/{summary.get('total', 0)} "
        f"({summary.get('accuracy', 0.0):.1%}), 평균 {summary.get('mean_sec', 0.0):.2f}s, "
        f"최대 {summary.get('max_sec', 0.0):.2f}s, 시간 점수 {summary.get('time_score', 0.0):.3f}"
    )


def _version_cell(row: dict[str, Any] | None, version: str) -> str:
    if row is None:
        return f"{version}: 로그 없음"
    status = "정답" if row.get("ok") else "오답"
    refs = ", ".join(_evidence_refs(row)[:4]) or "근거 참조 없음"
    return (
        f"{status}, {_md(row.get('sec', 0.0))}s<br>"
        f"예측: {_md(row.get('prediction', ''), 220)}<br>"
        f"판정 이유: {_md(row.get('reason', ''), 180)}<br>근거: {_md(refs, 240)}"
    )


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# v22 vs v23 평가 비교",
        "",
        f"생성 시각: {_md(result.get('generated_at'))} (Asia/Seoul)",
        "",
        f"v22 실행: `{_md(result.get('inputs', {}).get('v22_run_dir'))}`  ",
        f"v23 실행: `{_md(result.get('inputs', {}).get('v23_run_dir'))}`",
        "",
        "## 세트별 요약",
        "",
        "| 세트 | v22 | v23 | 정답 수 변화 | 정확도 변화 | 시간 점수 변화 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for set_name, values in result.get("per_set", {}).items():
        old, new, delta = values.get("v22"), values.get("v23"), values.get("delta", {})
        lines.append(
            f"| {set_name} | {_md(_fmt_summary(old))} | {_md(_fmt_summary(new))} | "
            f"{delta.get('correct', 0):+d} | {delta.get('accuracy', 0.0):+.1%} | {delta.get('time_score', 0.0):+.3f} |"
        )

    lines.extend(["", "## 수용 기준", "", "| 기준 | 결과 | 설명 |", "|---|---|---|"])
    labels = {
        "sample3_all_repeats_3_of_3": "sample3 3회 반복 모두 3/3",
        "all_v23_responses_under_19s": "v23 전체 응답시간 19초 미만",
        "v23_run_contains_expected_sets": "v23 전체 53문항 로그 존재",
        "sample_repeat_runs_are_distinct_and_complete": "sample3 반복 로그 3개 완비",
        "hard20_accuracy_drop_at_most_2": "hard20 정답 수 하락 2문항 이하",
        "holdout10_accuracy_drop_at_most_2": "holdout10 정답 수 하락 2문항 이하",
        "drive20_comparison_complete": "drive20 20문항 비교 완비",
        "clean_notebook_execution": "클린 노트북 실행 성공",
        "f2_reproduction_repair_observed": "F2 재현 문항에서 교정 발동",
    }
    for key, label in labels.items():
        check = result.get("acceptance_checks", {}).get(key, {})
        passed = check.get("passed")
        state = "확인 필요" if passed is None else ("예" if passed else "아니오")
        details = check.get("note") or check.get("criterion") or json.dumps(check, ensure_ascii=False)
        lines.append(f"| {label} | {state} | {_md(details, 300)} |")

    lines.extend(["", "## sample3 반복", ""])
    for item in result.get("sample_repeat_results", []):
        lines.append(
            f"- 반복 {item.get('repeat')}: {_fmt_summary(item.get('summary'))}; "
            f"3/3 통과: {'예' if item.get('is_3_of_3') else '아니오'} ({_md(item.get('run_dir'))})"
        )

    for set_name in ("hard20", "holdout10"):
        lines.extend(["", f"## {set_name} 정확도 회귀", ""])
        regressions = result.get("regressions", {}).get(set_name, [])
        if not regressions:
            lines.append("로그에서 v22 정답 → v23 오답으로 바뀐 문항을 찾지 못했습니다.")
        for item in regressions:
            lines.append(
                f"- #{_md(item.get('id'))} {_md(item.get('question'), 300)}  "
                f"v22 예측: {_md((item.get('v22') or {}).get('prediction', ''), 240)}  "
                f"v23 예측: {_md((item.get('v23') or {}).get('prediction', ''), 240)}  "
                f"설명: {_md(item.get('explanation'), 700)}"
            )

    drive = result.get("drive20", {})
    lines.extend([
        "",
        "## drive20 문항별 결과",
        "",
        f"v22 {drive.get('v22_count', 0)}문항, v23 {drive.get('v23_count', 0)}문항, "
        f"매칭 {drive.get('matched_count', 0)}문항. 아래 표는 저장된 두 실행의 모든 drive20 문항을 포함합니다.",
        "",
        "| ID | 질문 | v22 | v23 | 비교 설명 |",
        "|---:|---|---|---|---|",
    ])
    for item in drive.get("outcomes", []):
        lines.append(
            f"| {_md(item.get('id'))} | {_md(item.get('question'), 250)} | "
            f"{_version_cell(item.get('v22'), 'v22')} | {_version_cell(item.get('v23'), 'v23')} | "
            f"{_md(item.get('explanation'), 700)} |"
        )
    lines.extend(["", "## 클린 노트북 실행", ""])
    clean = result.get("clean_run", {})
    check = result.get("acceptance_checks", {}).get("clean_notebook_execution", {})
    lines.append(
        f"결과: {'성공' if check.get('passed') else '실패'}; "
        f"{clean.get('code_cell_count', '—')}개 코드 셀, 실패 {clean.get('failed_cell_count', '—')}개, "
        f"총 {clean.get('total_cell_wall_seconds', '—')}초. 파일: `{_md(clean.get('notebook', '—'))}`"
    )
    lines.extend(["", result.get("analysis_basis", ""), ""])
    return "\n".join(lines)


def write_comparison(result: dict[str, Any], json_path: str | Path, markdown_path: str | Path) -> None:
    json_target = Path(json_path)
    markdown_target = Path(markdown_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_target.write_text(render_markdown(result), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="저장된 v22/v23 실행 결과를 비교합니다. 평가/API 호출은 하지 않습니다.")
    parser.add_argument("--v22", required=True, help="v22 평가 실행 폴더")
    parser.add_argument("--v23", required=True, help="v23 평가 실행 폴더")
    parser.add_argument("--samples", required=True, action="append", help="v23 sample3 반복 실행 폴더. 세 번 지정")
    parser.add_argument("--clean", required=True, help="클린 노트북 실행 clean.json 경로")
    parser.add_argument("--f2-trace", default=str(ROOT / "eval" / "f2_repair_trace.json"),
                        help="API-free F2 재현 trace JSON")
    parser.add_argument("--output-json", default=str(ROOT / "eval" / "results_v23.json"))
    parser.add_argument("--output-markdown", default=str(ROOT / "runs" / "v23_comparison.md"))
    args = parser.parse_args(argv)
    if len(args.samples) != 3:
        parser.error("--samples를 sample3 반복 실행 폴더 세 개와 함께 정확히 세 번 지정하세요.")
    sample_dirs = [str(Path(path).expanduser().resolve()) for path in args.samples]
    if len(set(sample_dirs)) != 3:
        parser.error("--samples에는 서로 다른 세 반복 실행 폴더를 지정하세요.")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    v22 = load_run(args.v22)
    v23 = load_run(args.v23)
    sample_runs = [load_run(path) for path in args.samples]
    clean_path = Path(args.clean).expanduser().resolve()
    clean = _read_json(clean_path)
    if not isinstance(clean, dict):
        raise ValueError("clean.json은 JSON object여야 합니다.")
    clean["_path"] = str(clean_path)
    f2_path = Path(args.f2_trace).expanduser().resolve()
    f2_trace = _read_json(f2_path) if f2_path.is_file() else None
    result = build_comparison(v22, v23, sample_runs, clean, f2_trace=f2_trace)
    write_comparison(result, args.output_json, args.output_markdown)
    print(f"비교 결과 저장: {Path(args.output_json).resolve()}")
    print(f"보고서 조각 저장: {Path(args.output_markdown).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
