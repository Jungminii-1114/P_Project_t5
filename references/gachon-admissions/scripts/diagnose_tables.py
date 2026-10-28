"""Summarize saved table IR without API calls or pipeline imports."""

import argparse
from collections import Counter
import json
from pathlib import Path

from docparse.ir import Table
from docparse.render import header_records, html_full


def distribution(values):
    values = sorted(values)
    if not values:
        return {}
    return {"min": values[0], "p50": values[len(values)//2],
            "p90": values[int(len(values)*0.90)], "p95": values[int(len(values)*0.95)],
            "max": values[-1]}


def diagnose(path, limit=12000):
    tables = [Table.from_json(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]
    counts = Counter(t.origin for t in tables)
    uncertain = sum(t.confidence != "confident" for t in tables)
    lengths = [{"table_id": t.table_id, "source": t.source, "page": t.page,
                "confidence": t.confidence, "html_full": len(html_full(t)),
                "header_records": len("\n".join(s for _, s in header_records(t)))} for t in tables]
    pdf_count = sum(t.origin.startswith("pdf_") for t in tables)
    cells = sum(t.diagnostics.get("cell_text_comparison", {}).get("cells", 0) for t in tables)
    differences = sum(len(t.diagnostics.get("cell_text_comparison", {}).get("differences", [])) for t in tables)
    return {"tables": len(tables), "origin_counts": dict(counts),
        "origin_ratios": {key: count/len(tables) for key, count in counts.items()},
        "pdf_fallback_ratio": counts["pdf_fallback"]/pdf_count if pdf_count else 0,
        "uncertain_tables": uncertain, "uncertain_ratio": uncertain/len(tables) if tables else 0,
        "multilevel_header_tables": sum(t.header_rows > 1 for t in tables),
        "crop_comparison": {"cells": cells, "different_cells": differences,
                            "tables_with_differences": sum(bool(t.diagnostics.get("cell_text_comparison", {}).get("differences")) for t in tables)},
        "table_full_max_chars": limit,
        "length_distribution": {key: distribution([v[key] for v in lengths]) for key in ("html_full", "header_records")},
        "confident_length_distribution": {key: distribution([v[key] for v in lengths if v["confidence"] == "confident"]) for key in ("html_full", "header_records")},
        "over_limit": {key: [v for v in lengths if v[key] > limit] for key in ("html_full", "header_records")},
        "lengths": lengths,
        "scope_note": "Counts cover retained baseline tables. Undetected borderless tables are not counted as recovered PDF fallback tables."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir", type=Path, default=Path("runs/baseline2/ir/table_ir.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("reference/baseline2/metrics/structure.json"))
    args = parser.parse_args()
    result = diagnose(args.ir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in {"lengths", "over_limit"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
