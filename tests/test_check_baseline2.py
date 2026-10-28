"""Ensure inherited report text cannot hide a newly copied evaluation sentence."""
import json
import subprocess

import pytest

from scripts import check_baseline2


def test_audit_distinguishes_inherited_text_from_duplicate_or_new_file_leaks(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    (tmp_path / "eval").mkdir()
    sentence = "Synthetic evaluation question used only by this audit test."
    (tmp_path / "eval/testset_example.json").write_text(
        json.dumps([{"q": sentence}]), encoding="utf-8")
    report = tmp_path / "history.md"
    report.write_text(sentence + "\n", encoding="utf-8")
    git("add", ".")
    git("-c", "user.name=Audit Test", "-c", "user.email=audit@example.invalid", "commit", "-m", "fixture")
    git("tag", "baseline-1")
    monkeypatch.setattr(check_baseline2, "ROOT", tmp_path)
    monkeypatch.setattr(check_baseline2, "_sample_path", lambda _: tmp_path / "eval/testset_example.json")

    report.write_text(sentence + "\nNew session with no copied evaluation text.\n", encoding="utf-8")
    inherited = check_baseline2.audit()
    assert inherited["passed"]
    assert inherited["inherited_full_sentence_matches"]

    report.write_text(sentence + "\n" + sentence, encoding="utf-8")
    duplicate = check_baseline2.audit()
    assert not duplicate["passed"]
    assert duplicate["full_sentence_leaks"][0]["current_count"] == 2

    report.write_text(sentence, encoding="utf-8")
    (tmp_path / "new_report.md").write_text(sentence, encoding="utf-8")
    new_file = check_baseline2.audit()
    assert not new_file["passed"]
    assert any(match["file"] == "new_report.md" for match in new_file["full_sentence_leaks"])


def _init_audit_repo(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    (tmp_path / "eval").mkdir()
    sentence = "Synthetic evaluation question used only by this audit test."
    (tmp_path / "eval/testset_example.json").write_text(
        json.dumps([{"q": sentence}]), encoding="utf-8")
    git("add", ".")
    git("-c", "user.name=Audit Test", "-c", "user.email=audit@example.invalid", "commit", "-m", "fixture")
    git("tag", "baseline-1")
    monkeypatch.setattr(check_baseline2, "ROOT", tmp_path)
    monkeypatch.setattr(check_baseline2, "_sample_path", lambda _: tmp_path / "eval/testset_example.json")
    return sentence


def test_v24_run_jsonl_allows_question_content_but_is_scanned(tmp_path, monkeypatch):
    sentence = _init_audit_repo(tmp_path, monkeypatch)
    run_results = tmp_path / "eval/runs_v24/V0/results.jsonl"
    run_results.parent.mkdir(parents=True)
    run_results.write_text(json.dumps({"question": sentence}) + "\n", encoding="utf-8")

    result = check_baseline2.audit()

    assert result["passed"]
    assert "eval/runs_v24/V0/results.jsonl" in result["scanned_files"]
    assert not result["full_sentence_leaks"]


@pytest.mark.parametrize("relative_path", [
    "eval/runs_v24_backup/V0/results.jsonl",
    "eval/runs_v25/V0/results.jsonl",
    "eval/other_results.jsonl",
    "docs/report.md",
    "scripts/report.py",
])
def test_v24_question_allowlist_does_not_apply_to_other_paths(tmp_path, monkeypatch, relative_path):
    sentence = _init_audit_repo(tmp_path, monkeypatch)
    report = tmp_path / relative_path
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(sentence, encoding="utf-8")

    result = check_baseline2.audit()

    assert not result["passed"]
    assert any(match["file"] == relative_path for match in result["full_sentence_leaks"])


def test_v24_jsonl_allowlist_does_not_disable_secret_scanning(tmp_path, monkeypatch):
    sentence = _init_audit_repo(tmp_path, monkeypatch)
    run_results = tmp_path / "eval/runs_v24/V0/results.jsonl"
    run_results.parent.mkdir(parents=True)
    fake_key = "sk-" + "A" * 12
    run_results.write_text(json.dumps({"question": sentence, "key": fake_key}) + "\n", encoding="utf-8")

    result = check_baseline2.audit()

    assert any(match == {"file": "eval/runs_v24/V0/results.jsonl", "pattern": "openai_sk"}
               for match in result["secret_matches"])
    assert not result["full_sentence_leaks"]
    assert not result["passed"]
