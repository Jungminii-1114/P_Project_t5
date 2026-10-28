import json

from scripts.compare_eval import build_comparison, load_run, render_markdown, write_comparison


def test_accuracy_acceptance_uses_net_correct_count_and_reports_each_regression():
    old = [_row("hard20", i, i <= 17, "old", "reason") for i in range(1, 21)]
    new = [_row("hard20", i, i >= 4, "new", "reason") for i in range(1, 21)]
    result = build_comparison(_run("v22", old), _run("v23", new), [], {})
    check = result["acceptance_checks"]["hard20_accuracy_drop_at_most_2"]
    assert check["passed"] is True
    assert check["correct_count_drop"] == 0
    assert check["observed_regressions"] == 3


def test_f2_acceptance_checks_explicit_reproduction_trace():
    trace = {"action": "repair", "ground": {"pair_ok": 1.0},
             "events": [{"stage": "repair", "unsupported_pairs": [["가상학과", "77"]]}]}
    result = build_comparison(_run("old", []), _run("new", []), [], {}, f2_trace=trace)
    assert result["acceptance_checks"]["f2_reproduction_repair_observed"]["passed"] is True


def _row(set_name, item_id, ok, prediction, reason, sec=4.0, **extra):
    return {
        "set": set_name,
        "id": item_id,
        "question": f"질문 {item_id}",
        "gold": f"정답 {item_id}",
        "prediction": prediction,
        "ok": ok,
        "reason": reason,
        "sec": sec,
        "time_score": 0.4 if ok and sec <= 5 else 0,
        "evidence": [{"source": f"doc-{item_id}.pdf", "page": item_id, "kind": "text", "chunk": "근거"}],
        "ground": {"score": 0.9, "pair_ok": 1.0, "cite_ok": 1.0},
        **extra,
    }


def _run(path, rows):
    return {"path": str(path), "rows": rows, "summaries": None, "saved_summary": None}


def test_load_run_derives_summary_from_saved_jsonl(tmp_path):
    run_dir = tmp_path / "v22"
    run_dir.mkdir()
    rows = [_row("hard20", 1, True, "예측", "일치", 4.0), _row("hard20", 2, False, "틀림", "누락", 7.0)]
    (run_dir / "results.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    loaded = load_run(run_dir)

    assert loaded["summaries"]["hard20"]["correct"] == 1
    assert loaded["summaries"]["hard20"]["total"] == 2
    assert loaded["summaries"]["hard20"]["time_score"] == 0.4
    assert loaded["summary_source"] == "results.jsonl"


def test_comparison_has_acceptance_checks_regressions_and_all_drive_outcomes():
    v22 = _run("v22", [
        _row("hard20", 1, True, "old correct", "일치"),
        _row("holdout10", 1, True, "old correct", "일치"),
        _row("drive20", 1, True, "drive old", "일치"),
        _row("drive20", 2, False, "old fail", "누락"),
        _row("drive20", 3, True, "same", "일치"),
        *[_row("hard20", n, True, f"hard {n}", "일치") for n in range(2, 21)],
        *[_row("holdout10", n, True, f"holdout {n}", "일치") for n in range(2, 11)],
        *[_row("drive20", n, True, f"drive {n}", "일치") for n in range(4, 21)],
        *[_row("sample3", n, True, f"sample {n}", "일치") for n in range(1, 4)],
    ])
    v23 = _run("v23", [
        _row("hard20", 1, False, "new fail", "수치 누락"),
        _row("holdout10", 1, True, "new correct", "핵심 일치"),
        _row("drive20", 1, False, "drive failed", "조건 누락", events=[{"stage": "repair", "trigger": "repair"}]),
        _row("drive20", 2, True, "new success", "핵심 일치"),
        _row("drive20", 3, True, "same", "일치"),
        *[_row("hard20", n, True, f"hard {n}", "일치") for n in range(2, 21)],
        *[_row("holdout10", n, True, f"holdout {n}", "일치") for n in range(2, 11)],
        *[_row("drive20", n, True, f"drive {n}", "일치") for n in range(4, 21)],
        *[_row("sample3", n, True, f"sample {n}", "일치") for n in range(1, 4)],
    ])
    sample_runs = [
        _run(f"sample-{index}", [_row("sample3", n, True, f"s{n}", "일치") for n in range(1, 4)])
        for index in range(1, 4)
    ]
    clean = {"notebook": "clean.ipynb", "code_cell_count": 10, "failed_cell_count": 0, "total_cell_wall_seconds": 12.0}

    result = build_comparison(v22, v23, sample_runs, clean, generated_at="2026-10-28T15:00:00+09:00")

    assert result["per_set"]["hard20"]["v22"]["correct"] == 20
    assert result["per_set"]["hard20"]["v23"]["correct"] == 19
    assert len(result["regressions"]["hard20"]) == 1
    assert result["regressions"]["hard20"][0]["explanation"]
    assert result["acceptance_checks"]["sample3_all_repeats_3_of_3"]["passed"] is True
    assert result["acceptance_checks"]["clean_notebook_execution"]["passed"] is True
    assert result["acceptance_checks"]["v23_run_contains_expected_sets"]["passed"] is True
    assert result["acceptance_checks"]["hard20_accuracy_drop_at_most_2"]["passed"] is True
    assert len(result["drive20"]["outcomes"]) == 20
    assert result["drive20"]["outcomes"][0]["status"] == "regression"
    assert result["drive20"]["outcomes"][1]["status"] == "improvement"
    assert result["drive20"]["outcomes"][2]["status"] == "unchanged_correct"
    assert all(row["explanation"] for row in result["drive20"]["outcomes"])


def test_markdown_includes_every_drive_item_and_explanations_for_failures():
    v22 = _run("v22", [_row("drive20", 1, False, "old", "숫자 누락")])
    v23 = _run("v23", [_row("drive20", 1, False, "new", "날짜 누락")])
    samples = [_run(f"sample-{index}", [_row("sample3", n, True, "ok", "일치") for n in range(1, 4)]) for index in range(3)]
    result = build_comparison(v22, v23, samples, {"code_cell_count": 1, "failed_cell_count": 0}, generated_at="2026-10-28T15:00:00+09:00")

    markdown = render_markdown(result)

    assert "drive20" in markdown
    assert "질문 1" in markdown
    assert "날짜 누락" in markdown
    assert "doc-1.pdf p.1" in markdown


def test_writer_creates_json_and_markdown_outputs(tmp_path):
    v22 = _run("v22", [_row("drive20", 1, True, "old", "일치")])
    v23 = _run("v23", [_row("drive20", 1, True, "new", "일치")])
    samples = [_run(f"sample-{index}", [_row("sample3", n, True, "ok", "일치") for n in range(1, 4)]) for index in range(3)]
    result = build_comparison(v22, v23, samples, {"code_cell_count": 1, "failed_cell_count": 0}, generated_at="2026-10-28T15:00:00+09:00")
    json_path, md_path = tmp_path / "results.json", tmp_path / "comparison.md"

    write_comparison(result, json_path, md_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["drive20"]["outcomes"][0]["id"] == 1
    assert "# v22 vs v23" in md_path.read_text(encoding="utf-8")
