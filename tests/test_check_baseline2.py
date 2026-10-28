"""Ensure inherited report text cannot hide a newly copied evaluation sentence."""
import json
import subprocess

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
