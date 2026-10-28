"""Audit frozen scope, secrets, and full evaluation-sentence leakage locally."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from scripts.check_notebook import SECRET_PATTERNS
from scripts.run_eval import _records, _sample_path


ROOT = Path(__file__).resolve().parents[1]


def audit():
    frozen = ["reference/baseline1", "legacy", "build_notebook.py",
              "pipeline_v23.py", "202235052_박진성.ipynb"]
    diff = subprocess.check_output(["git", "diff", "baseline-1", "--", *frozen], cwd=ROOT)
    tracked = subprocess.check_output(["git", "diff", "--name-only", "baseline-1", "-z"], cwd=ROOT)
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=ROOT)
    names = sorted(set(s.decode("utf-8") for s in (tracked+untracked).split(b"\0") if s))
    corpus = []
    dataset_paths = sorted((ROOT / "eval").glob("testset_*.json"))
    try:
        dataset_paths.append(_sample_path(None))
    except FileNotFoundError:
        pass
    for path in dataset_paths:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        for index, item in enumerate(_records(payload), 1):
            for key in ("q", "question", "gold", "sample answer", "sample_answer", "answer"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    corpus.append((path.name, index, key, value))
    secrets, leaks, hashes = [], [], {}
    for name in names:
        path = ROOT / name
        if not path.is_file() or path.suffix not in {".py", ".md", ".json", ".yaml", ".toml"}:
            continue
        content = path.read_text(encoding="utf-8-sig")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                secrets.append({"file": name, "pattern": label})
        for dataset, index, key, value in corpus:
            if value in content:
                leaks.append({"file": name, "dataset": dataset, "item": index, "field": key})
    return {"frozen_scope_unchanged": not diff, "secret_matches": secrets,
            "full_sentence_leaks": leaks, "scanned_files": hashes,
            "passed": not diff and not secrets and not leaks,
            "note": "The literal reference/ diff includes the required new baseline2 documentation; frozen baseline1 is checked separately."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "runs/baseline2/static_audit.json")
    args = parser.parse_args()
    result = audit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "scanned_files"}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
