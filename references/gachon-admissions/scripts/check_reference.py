"""Audit committed reference material without printing secrets or evaluation text."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_notebook import SECRET_PATTERNS, find_entries
from scripts.run_eval import load_dataset


def audit(root: Path = ROOT) -> dict:
    paths = sorted(p for p in (root / "reference").rglob("*")
                   if p.suffix in {".py", ".md", ".json"})
    paths += [root / "BACKLOG.md", root / "scripts/snapshot_parse.py",
              root / "scripts/check_reference.py"]
    paths += sorted((root / "tests").glob("test_reference*.py"))
    texts = {p: p.read_text(encoding="utf-8") for p in paths if p.is_file()}
    secrets = []
    for path, content in texts.items():
        for name, pattern in SECRET_PATTERNS.items():
            count = len(pattern.findall(content))
            if count:
                secrets.append({"path": path.relative_to(root).as_posix(),
                                "pattern": name, "count": count})
    overlap = []
    normalized = {p: re.sub(r"\s+", " ", s) for p, s in texts.items()}
    datasets = []
    for dataset in sorted((root / "eval").glob("testset*.json")):
        payload = json.loads(dataset.read_text(encoding="utf-8-sig"))
        datasets.append((dataset.name, payload))
    try:
        datasets.append(("sample3", load_dataset("sample3")))
        sample_found = True
    except FileNotFoundError:
        sample_found = False
    for dataset_name, payload in datasets:
        for label, value in find_entries(payload, {"q", "question", "gold"}):
            needle = re.sub(r"\s+", " ", value).strip()
            if not needle:
                continue
            for path, content in normalized.items():
                if needle in content:
                    overlap.append({"set": dataset_name, "item": label,
                                    "path": path.relative_to(root).as_posix()})
    return {"file_count": len(texts), "sample3_checked": sample_found,
            "secret_matches": secrets,
            "evaluation_sentence_matches": overlap,
            "passed": not secrets and not overlap,
            "scope": "Full q/question/gold values, with whitespace normalized; counts and IDs only."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
