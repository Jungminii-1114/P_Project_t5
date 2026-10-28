"""Compare source-authored table facts with saved IR, preserving every failure."""

import argparse
import json
from pathlib import Path

from docparse.ir import Table, table_id


def _text(value):
    return "".join(value.split())


def _path(value):
    return [_text(v) for v in value]


def compare_table(golden, table):
    expected = golden["expected"]
    comparisons = []
    for sample in expected["samples"]:
        actual = None
        if table is not None and "coordinate" in sample:
            row, col = sample["coordinate"]
            cell = table.cell_at(row, col)
            if cell:
                actual = {"row_label": table.row_label(row),
                          "header_path": table.header_path(col), "value": cell.text}
        # Nested visual tables have no IR cell coordinate: an exact semantic
        # triple is still eligible to match anywhere in the enclosing table.
        if actual is None and table is not None and "coordinate" not in sample:
            for row in range(table.header_rows, table.n_rows):
                for col in range(table.stub_cols, table.n_cols):
                    cell = table.cell_at(row, col)
                    candidate = {"row_label": table.row_label(row),
                                 "header_path": table.header_path(col),
                                 "value": cell.text if cell else ""}
                    if all((_text(candidate[k]) == _text(sample[k]) if k == "value" else
                            _path(candidate[k]) == _path(sample[k])) for k in candidate):
                        actual = candidate
                        break
                if actual:
                    break
        checks = {key: actual is not None and (
            _text(actual[key]) == _text(sample[key]) if key == "value" else
            _path(actual[key]) == _path(sample[key])) for key in ("row_label", "header_path", "value")}
        comparisons.append({"coordinate": sample.get("coordinate"), "expected": {
            key: sample[key] for key in ("row_label", "header_path", "value")},
            "actual": actual, "checks": checks, "passed": all(checks.values())})
    structure = {"header_rows": table is not None and table.header_rows == expected["header_rows"],
                 "stub_cols": table is not None and table.stub_cols == expected["stub_cols"]}
    return {"id": golden["id"], "source": golden["source"], "page": golden.get("page"),
            "locator": golden.get("locator"), "type": golden["type"], "found": table is not None,
            "structure_checks": structure, "actual_structure": {
                "header_rows": table.header_rows, "stub_cols": table.stub_cols,
                "confidence": table.confidence} if table else None,
            "samples": comparisons, "passed": all(structure.values()) and all(c["passed"] for c in comparisons)}


def compare(golden_path, ir_path):
    goldens = json.loads(Path(golden_path).read_text(encoding="utf-8-sig"))
    registry = {table.table_id: table for line in Path(ir_path).read_text(encoding="utf-8").splitlines()
                if (table := Table.from_json(line))}
    results = []
    for golden in goldens["tables"]:
        locator = golden.get("locator", {"type": "page", "value": golden.get("page")})
        ordinal = 0 if golden["source"].lower().endswith(".hwp") else golden["table_ordinal"]
        table = registry.get(table_id(golden["source"], locator, ordinal))
        results.append(compare_table(golden, table))
    samples = [s for result in results for s in result["samples"]]
    return {"tables": results, "summary": {"tables_passed": sum(r["passed"] for r in results),
        "tables_total": len(results), "cells_passed": sum(s["passed"] for s in samples),
        "cells_total": len(samples), "value_only_passed": sum(s["checks"]["value"] for s in samples)},
        "user_review_status": "pending", "normalization": "Whitespace only; no aliases or document-specific correction.",
        "limitations": "Source-grid coordinates may differ between extraction libraries. Nested visual tables require real IR cells. Logical headers following title/spacer rows are compared strictly to the current top-contiguous IR header count.",
        "all_passed": all(r["passed"] for r in results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=Path("tests/golden/tables.yaml"))
    parser.add_argument("--ir", type=Path, default=Path("runs/baseline2/ir/table_ir.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("reference/baseline2/metrics/golden.json"))
    parser.add_argument("--strict", action="store_true", help="Return nonzero if any source expectation fails")
    args = parser.parse_args()
    result = compare(args.golden, args.ir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 1 if args.strict and not result["all_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
