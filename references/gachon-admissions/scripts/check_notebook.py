"""Check a generated notebook for syntax, saved outputs, and embedded answer/key text.

The report deliberately includes only counts and cell/item indexes. It never prints
API key candidates, evaluation gold text, or official sample answer values.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
WINDOW_SIZE = 8

SECRET_PATTERNS = {
    "openai_sk": re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    "voyage_pa": re.compile(r"\bpa-[A-Za-z0-9_-]{12,}\b"),
    "voyage_token": re.compile(r"\b(?:vua|voyage)[_-][A-Za-z0-9_-]{12,}\b", re.I),
    "google_api": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "anthropic": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{12,}\b"),
}

SAMPLE_VALUE_PATTERNS = (
    re.compile(r"(?<!\d)\d{2,4}[- ]\d{3,4}[- ]\d{4}(?!\d)"),
    re.compile(r"(?<!\d)\d{4}[-/.]\d{1,2}(?:[-/.]\d{1,2})?(?!\d)"),
    re.compile(r"(?<!\d)\d{1,2}월\s*\d{1,2}일"),
    re.compile(r"(?<!\d)\d+(?:\.\d+)?\s*(?:원|만원|명|개월|주|일|년|월|시|분|초|%)"),
    re.compile(r"(?<!\d)\d{5,}(?!\d)"),
)


def cell_source(cell: dict[str, Any]) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def strip_pip_lines(source: str) -> str:
    """Remove notebook %pip magic lines before Python syntax compilation."""
    lines = source.splitlines(keepends=True)
    return "".join(
        ("\n" if line.endswith("\n") else "") if line.lstrip().startswith("%pip") else line
        for line in lines
    )


def text_windows(text: str, size: int = WINDOW_SIZE) -> set[str]:
    if len(text) < size:
        return set()
    return {text[i : i + size] for i in range(len(text) - size + 1)}


def index_label(path: tuple[int, ...]) -> str:
    return ".".join(str(part) for part in path) if path else "root"


def _string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _string_values(item)


def find_entries(value: Any, wanted_keys: set[str], path: tuple[int, ...] = ()) -> list[tuple[str, str]]:
    """Find string/list values under matching keys, retaining item indexes only."""
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[\s_-]+", "", str(key).casefold())
            if normalized in wanted_keys:
                found.extend((index_label(path), text) for text in _string_values(child))
            else:
                found.extend(find_entries(child, wanted_keys, path))
    elif isinstance(value, list):
        for i, child in enumerate(value, start=1):
            found.extend(find_entries(child, wanted_keys, path + (i,)))
    return found


def find_default_sample() -> Path | None:
    repo_sample = ROOT / "sample.json"
    if repo_sample.is_file():
        return repo_sample
    downloads = Path.home() / "Downloads"
    matches = sorted(downloads.glob("중간평가-*/중간평가/sample.json"))
    return matches[0] if matches else None


def sample_value_tokens(answer: str) -> set[str]:
    tokens: set[str] = set()
    for pattern in SAMPLE_VALUE_PATTERNS:
        tokens.update(match.group(0) for match in pattern.finditer(answer))
    return tokens


def inspect_eval_gold(eval_dir: Path, notebook_cells: list[str]) -> dict[str, Any]:
    notebook_windows = set().union(*(text_windows(text) for text in notebook_cells))
    file_reports: list[dict[str, Any]] = []
    overlap_items: list[dict[str, Any]] = []
    all_entry_windows: dict[tuple[str, str], set[str]] = {}

    files = sorted(eval_dir.glob("*.json")) if eval_dir.is_dir() else []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            file_reports.append({
                "set": path.name,
                "read_error": type(exc).__name__,
            })
            continue

        entries = find_entries(payload, {"gold"})
        file_windows: set[str] = set()
        matched_windows = 0
        matched_item_count = 0
        for label, gold in entries:
            windows = text_windows(gold)
            matches = windows & notebook_windows
            file_windows.update(windows)
            all_entry_windows[(path.name, label)] = windows
            if matches:
                matched_item_count += 1
                matched_windows += len(matches)
                overlap_items.append({
                    "set": path.name,
                    "index": label,
                    "window_count": len(matches),
                })
        file_reports.append({
            "set": path.name,
            "gold_item_count": len(entries),
            "distinct_window_count": len(file_windows),
            "overlap_item_count": matched_item_count,
            "overlap_window_count": matched_windows,
        })

    owner_count: dict[str, int] = defaultdict(int)
    for windows in all_entry_windows.values():
        for window in windows:
            owner_count[window] += 1
    shared_overlap_count = 0
    for item in overlap_items:
        windows = all_entry_windows[(item["set"], item["index"])]
        shared_for_item = sum(
            1 for window in windows & notebook_windows if owner_count[window] > 1
        )
        item["shared_window_count"] = shared_for_item
        shared_overlap_count += shared_for_item

    return {
        "json_file_count": len(files),
        "read_error_count": sum("read_error" in item for item in file_reports),
        "gold_item_count": sum(int(item.get("gold_item_count", 0)) for item in file_reports),
        "sets": file_reports,
        "overlap_items": overlap_items,
        "shared_overlap_window_count": shared_overlap_count,
    }


def inspect_sample_answers(sample_path: Path | None, notebook_cells: list[str]) -> dict[str, Any]:
    if sample_path is None or not sample_path.is_file():
        return {"found": False, "answer_item_count": 0, "overlap_items": []}

    try:
        payload = json.loads(sample_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"found": True, "read_error": type(exc).__name__, "overlap_items": []}

    notebook_text = "\n".join(notebook_cells)
    notebook_windows = set().union(*(text_windows(text) for text in notebook_cells))
    entries = find_entries(payload, {"sampleanswer", "answer"})
    overlaps: list[dict[str, Any]] = []
    for label, answer in entries:
        matched_windows = text_windows(answer) & notebook_windows
        matched_values = {token for token in sample_value_tokens(answer) if token in notebook_text}
        if matched_windows or matched_values:
            overlaps.append({
                "index": label,
                "window_count": len(matched_windows),
                "value_token_count": len(matched_values),
            })
    return {
        "found": True,
        "answer_item_count": len(entries),
        "overlap_items": overlaps,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--notebook",
        type=Path,
        default=ROOT / "202235052_박진성.ipynb",
        help="Notebook to inspect (default: workspace submission notebook).",
    )
    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=ROOT / "eval",
        help="Directory containing evaluation JSON files.",
    )
    parser.add_argument(
        "--sample",
        type=Path,
        help="Official sample.json path; auto-discovered under Downloads when omitted.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    notebook_path = args.notebook if args.notebook.is_absolute() else ROOT / args.notebook
    eval_dir = args.eval_dir if args.eval_dir.is_absolute() else ROOT / args.eval_dir
    sample_path = args.sample or find_default_sample()
    if sample_path is not None and not sample_path.is_absolute():
        sample_path = ROOT / sample_path

    if not notebook_path.is_file():
        print(json.dumps({"error": "notebook_not_found"}, ensure_ascii=False))
        return 2

    try:
        payload = json.loads(notebook_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": type(exc).__name__}, ensure_ascii=False))
        return 2

    cells = payload.get("cells", [])
    code_cells = [(i + 1, cell_source(cell)) for i, cell in enumerate(cells) if cell.get("cell_type") == "code"]
    syntax_errors: list[dict[str, Any]] = []
    output_cells: list[dict[str, Any]] = []
    for index, source in code_cells:
        try:
            compile(strip_pip_lines(source), f"{notebook_path.name}:cell-{index}", "exec")
        except SyntaxError as exc:
            syntax_errors.append({
                "cell": index,
                "line": exc.lineno,
                "error": type(exc).__name__,
                "message": exc.msg,
            })
    for index, cell in enumerate(cells, start=1):
        if cell.get("cell_type") != "code":
            continue
        outputs = cell.get("outputs", []) or []
        has_execution_count = cell.get("execution_count") is not None
        if outputs or has_execution_count:
            output_cells.append({
                "cell": index,
                "output_count": len(outputs),
                "has_execution_count": has_execution_count,
            })

    notebook_cells = [cell_source(cell) for cell in cells]
    notebook_text = "\n".join(notebook_cells)
    secret_counts = {
        name: len(pattern.findall(notebook_text))
        for name, pattern in SECRET_PATTERNS.items()
    }
    secret_count = sum(secret_counts.values())
    eval_report = inspect_eval_gold(eval_dir, notebook_cells)
    sample_report = inspect_sample_answers(sample_path, notebook_cells)

    passed = (
        not syntax_errors
        and not output_cells
        and secret_count == 0
        and not eval_report["overlap_items"]
        and eval_report["read_error_count"] == 0
        and eval_report["gold_item_count"] > 0
        and sample_report.get("found", False)
        and not sample_report.get("read_error")
        and not sample_report["overlap_items"]
    )
    report = {
        "notebook": str(notebook_path),
        "code_cell_count": len(code_cells),
        "syntax_errors": syntax_errors,
        "cells_with_outputs_or_execution_counts": output_cells,
        "api_key_pattern_counts": secret_counts,
        "api_key_pattern_total": secret_count,
        "eval_gold": eval_report,
        "official_sample_answers": {
            **sample_report,
            "path": str(sample_path) if sample_path is not None else None,
        },
        "passed": passed,
        "report_note": (
            "Only counts and indexes are reported. Repeated 8-character windows across "
            "multiple gold items are marked as shared overlap candidates; review those "
            "indexes for boilerplate without exposing gold text."
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
