"""Execute notebook code cells in a fresh Python process without editing the notebook.

The notebook's ``%pip`` lines are replaced with a confirmation that the locked uv
environment is already installed. Per-cell timing and exceptions are written under
``runs/<timestamp>_clean/clean.json``. Use ``--capture-stdout`` to include sanitized
cell output in that JSON file.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PIP_CONFIRMATION = "uv sync already installed the locked dependencies; notebook %pip install was skipped."
SECRET_TOKEN_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bpa-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:vua|voyage)[_-][A-Za-z0-9_-]{12,}\b", re.I),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
)


def cell_source(cell: dict[str, Any]) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def replace_pip_lines(source: str) -> tuple[str, int]:
    replaced = 0
    output: list[str] = []
    for line in source.splitlines(keepends=True):
        if line.lstrip().startswith("%pip"):
            indentation = line[: len(line) - len(line.lstrip())]
            newline = "\n" if line.endswith("\n") else ""
            output.append(indentation + "print(" + repr(PIP_CONFIRMATION) + ")" + newline)
            replaced += 1
        else:
            output.append(line)
    return "".join(output), replaced


def secret_values() -> list[str]:
    return sorted({
        value
        for name in ("OPENAI_API_KEY", "VOYAGEAI_API_KEY", "VOYAGE_API_KEY")
        if (value := os.environ.get(name)) and len(value) >= 6
    }, key=len, reverse=True)


def sanitize(text: str, values: list[str]) -> str:
    for value in values:
        text = text.replace(value, "[REDACTED]")
    for pattern in SECRET_TOKEN_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--notebook",
        type=Path,
        default=ROOT / "202235052_박진성.ipynb",
        help="Notebook to execute (default: workspace submission notebook).",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="Output directory; defaults to runs/<timestamp>_clean.",
    )
    parser.add_argument(
        "--capture-stdout",
        action="store_true",
        help="Include sanitized stdout/stderr for each code cell in clean.json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    notebook_path = args.notebook if args.notebook.is_absolute() else ROOT / args.notebook
    if not notebook_path.is_file():
        print(json.dumps({"error": "notebook_not_found"}, ensure_ascii=False))
        return 2

    try:
        notebook = json.loads(notebook_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": type(exc).__name__}, ensure_ascii=False))
        return 2

    if args.run_dir is None:
        stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
        run_dir = ROOT / "runs" / f"{stamp}_clean"
    else:
        run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(ROOT)

    redactions = secret_values()
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    namespace: dict[str, Any] = {
        "__name__": "__main__",
        "__file__": str(notebook_path.resolve()),
    }
    records: list[dict[str, Any]] = []

    for notebook_index, cell in enumerate(notebook.get("cells", []), start=1):
        if cell.get("cell_type") != "code":
            continue
        source, pip_lines_skipped = replace_pip_lines(cell_source(cell))
        captured_out = io.StringIO()
        captured_err = io.StringIO()
        started = time.perf_counter()
        error: dict[str, str] | None = None

        try:
            with contextlib.redirect_stdout(captured_out), contextlib.redirect_stderr(captured_err):
                exec(
                    compile(source, f"{notebook_path.name}:cell-{notebook_index}", "exec"),
                    namespace,
                    namespace,
                )
        except Exception as exc:  # Keep a record and continue with later notebook cells.
            error = {
                "type": type(exc).__name__,
                "message": sanitize(str(exc), redactions),
                "traceback": sanitize("".join(traceback.format_exception_only(type(exc), exc)).strip(), redactions),
            }

        duration = time.perf_counter() - started
        record: dict[str, Any] = {
            "cell": notebook_index,
            "status": "error" if error else "ok",
            "wall_seconds": round(duration, 6),
            "pip_lines_skipped": pip_lines_skipped,
        }
        if error:
            record["exception"] = error
        if args.capture_stdout:
            record["stdout"] = sanitize(captured_out.getvalue(), redactions)
            record["stderr"] = sanitize(captured_err.getvalue(), redactions)
        records.append(record)

    finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
    failures = [record for record in records if record["status"] == "error"]
    report = {
        "notebook": str(notebook_path.resolve()),
        "started_at": started_at,
        "finished_at": finished_at,
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "process_id": os.getpid(),
        "code_cell_count": len(records),
        "failed_cell_count": len(failures),
        "total_cell_wall_seconds": round(sum(record["wall_seconds"] for record in records), 6),
        "capture_stdout": bool(args.capture_stdout),
        "cells": records,
    }
    output_path = run_dir / "clean.json"
    if output_path.exists():
        print(json.dumps({"error": "clean_report_already_exists", "path": str(output_path)}, ensure_ascii=False))
        return 2
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "clean_json": str(output_path),
        "code_cell_count": len(records),
        "failed_cell_count": len(failures),
        "total_cell_wall_seconds": report["total_cell_wall_seconds"],
    }, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
