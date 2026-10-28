"""Render selected source pages and record source-only golden preparation evidence.

This helper reads only the ``src`` field from evaluation rows when checking PDF
page references. It never loads or emits evaluation questions or answers.
Generated PNGs and JSON references belong under runs/baseline2/golden/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
from langchain_hwp_hwpx import HwpHwpxLoader


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "dataset"
OUT = ROOT / "runs" / "baseline2" / "golden"
FIXTURE = ROOT / "tests" / "golden" / "tables.yaml"

PREFIX_TO_FILE = {
    "01": "01_2027학년도_재외국민_모집요강.hwp",
    "02": "02_2027학년도_지역의사선발전형_안내.pdf",
    "03": "03_2027학년도_수시_모집요강.pdf",
    "04": "04_2027학년도_정시_모집요강.pdf",
    "05": "05_2027학년도_수시_면접고사_일정.pdf",
}

PAGE_REFERENCE_CASES = [
    {
        "set": "holdout10",
        "item": 6,
        "expected_src": "04 p.35",
        "pages": [("04", 35)],
    },
    {
        "set": "drive20",
        "item": 17,
        "expected_src": "03 p.30, p.85, p.86",
        "pages": [("03", 30), ("03", 85), ("03", 86)],
    },
    {
        "set": "drive20",
        "item": 19,
        "expected_src": "05 p.2, p.3 / 03 p.33",
        "pages": [("05", 2), ("05", 3), ("03", 33)],
    },
]


def _read_fixture() -> dict:
    # tables.yaml intentionally uses JSON syntax, which is also valid YAML.
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _eval_src(set_name: str, item_number: int) -> str:
    path = ROOT / "eval" / f"testset_{'holdout' if set_name == 'holdout10' else set_name}.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    return str(rows[item_number - 1].get("src", ""))


def _first_text_lines(page: pymupdf.Page, n: int = 3) -> list[str]:
    return [line.strip() for line in page.get_text().splitlines() if line.strip()][:n]


def _render_and_inventory(fixture: dict) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    png_dir = OUT / "source_pngs"
    png_dir.mkdir(parents=True, exist_ok=True)
    inventory: list[dict] = []
    hwp_refs: list[dict] = []

    for fixture_index, table in enumerate(fixture["tables"]):
        source = table["source"]
        if source.lower().endswith(".pdf"):
            page_number = int(table["page"])
            doc = pymupdf.open(DATA / source)
            if not 1 <= page_number <= len(doc):
                raise ValueError(f"PDF page outside file: {source} p.{page_number}")
            page = doc[page_number - 1]
            found = page.find_tables()
            png_path = png_dir / f"{source[:2]}_p{page_number:03}.png"
            page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), alpha=False).save(png_path)

            extraction_status = table.get("extraction_status")
            if extraction_status == "not_separately_detected":
                if table.get("table_ordinal") is not None:
                    raise ValueError(
                        f"Visual-region fixtures must have a null table ordinal: {table.get('id')}"
                    )
                bbox = table.get("source_region_bbox")
                if not isinstance(bbox, list) or len(bbox) != 4:
                    raise ValueError(f"Visual-region fixture needs a four-value bbox: {table.get('id')}")
                region = pymupdf.Rect(*map(float, bbox))
                if region.is_empty or not page.rect.contains(region):
                    raise ValueError(f"Visual-region bbox is outside PDF page: {table.get('id')}")
                region_png = png_dir / (
                    f"{source[:2]}_p{page_number:03}_region_{fixture_index:02}.png"
                )
                page.get_pixmap(matrix=pymupdf.Matrix(3, 3), clip=region, alpha=False).save(region_png)
                samples = table.get("expected", {}).get("samples", [])
                if any("visual_coordinate" not in sample for sample in samples):
                    raise ValueError(
                        f"Visual-region samples need visual_coordinate fields: {table.get('id')}"
                    )
                inventory.append({
                    "id": table["id"],
                    "source": source,
                    "file_page": page_number,
                    "page_count": len(doc),
                    "table_ordinal": None,
                    "table_count_on_page": len(found.tables),
                    "extraction_status": extraction_status,
                    "separate_extraction_missing": True,
                    "native_grid_dimension_assertion": "skipped_visual_region",
                    "source_dimensions_visual": table.get("source_dimensions"),
                    "source_region_bbox": bbox,
                    "source_region_bbox_units": table.get("source_region_bbox_units"),
                    "visual_sample_count": len(samples),
                    "visual_samples": [
                        {
                            "visual_coordinate": sample["visual_coordinate"],
                            "row_label": sample["row_label"],
                            "header_path": sample["header_path"],
                            "value": sample["value"],
                        }
                        for sample in samples
                    ],
                    "page_text_prefix": _first_text_lines(page),
                    "png": str(png_path.relative_to(ROOT)),
                    "region_png": str(region_png.relative_to(ROOT)),
                })
                doc.close()
                continue
            if extraction_status is not None:
                raise ValueError(f"Unknown PDF extraction_status: {extraction_status!r}")

            ordinal = int(table["table_ordinal"])
            if not 0 <= ordinal < len(found.tables):
                raise ValueError(
                    f"Table ordinal {ordinal} unavailable: {source} file p.{page_number} "
                    f"has {len(found.tables)} find_tables() results"
                )
            rows = found.tables[ordinal].extract()
            expected_dims = table.get("source_dimensions", {})
            if len(rows) != expected_dims.get("rows"):
                raise ValueError(f"Row count changed for {table['id']}: {len(rows)}")
            if max((len(row) for row in rows), default=0) != expected_dims.get("cols"):
                raise ValueError(f"Column count changed for {table['id']}")
            sample_checks = []
            for sample in table["expected"]["samples"]:
                if "coordinate" not in sample:
                    continue  # The fixture marks this as an inset source grid.
                row, col = sample["coordinate"]
                if row >= len(rows) or col >= len(rows[row]):
                    raise ValueError(f"Sample coordinate outside table: {table['id']} {row},{col}")
                sample_checks.append({
                    "coordinate": [row, col],
                    "fixture_value": sample["value"],
                    "source_extracted_text": rows[row][col],
                })
            inventory.append({
                "id": table["id"],
                "source": source,
                "file_page": page_number,
                "page_count": len(doc),
                "table_ordinal": ordinal,
                "table_count_on_page": len(found.tables),
                "table_dimensions": {"rows": len(rows), "cols": max(map(len, rows), default=0)},
                "page_text_prefix": _first_text_lines(page),
                "png": str(png_path.relative_to(ROOT)),
                "sample_coordinate_checks": sample_checks,
            })
            doc.close()
        else:
            doc = HwpHwpxLoader(str(DATA / source), mode="elements", distribution_backend="pyhwp").load()
            locator_value = int(table["locator"]["value"])
            element = next(
                e for e in doc
                if e.metadata.get("element_type") == "table"
                and int(e.metadata.get("element_index", -1)) == locator_value
            )
            cells = json.loads(element.metadata.get("cells", "[]"))
            hwp_refs.append({
                "id": table["id"],
                "source": source,
                "locator": table["locator"],
                "table_ordinal": table["table_ordinal"],
                "cells": cells,
            })
            inventory.append({
                "id": table["id"],
                "source": source,
                "locator": table["locator"],
                "table_ordinal": table["table_ordinal"],
                "source_cell_count": len(cells),
            })

    inventory_path = OUT / "source_table_inventory.json"
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hwp_path = OUT / "hwp_cells_reference.json"
    hwp_path.write_text(json.dumps(hwp_refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"inventory": inventory, "inventory_path": inventory_path, "hwp_path": hwp_path}


def _validate_src_pages() -> list[dict]:
    evidence = []
    for case in PAGE_REFERENCE_CASES:
        src = _eval_src(case["set"], case["item"])
        if src != case["expected_src"]:
            raise ValueError(
                f"Evaluation src changed for {case['set']}#{case['item']}: {src!r}"
            )
        pages = []
        for prefix, page_number in case["pages"]:
            source = PREFIX_TO_FILE[prefix]
            doc = pymupdf.open(DATA / source)
            if not 1 <= page_number <= len(doc):
                raise ValueError(f"Source page outside file: {source} p.{page_number}")
            page = doc[page_number - 1]
            pages.append({
                "document": source,
                "file_page": page_number,
                "page_count": len(doc),
                "page_text_prefix": _first_text_lines(page),
            })
            doc.close()
        evidence.append({
            "set": case["set"],
            "item": case["item"],
            "src_only": src,
            "verified_file_pages": pages,
        })
    path = OUT / "page_number_validation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return evidence


def main() -> None:
    fixture = _read_fixture()
    rendered = _render_and_inventory(fixture)
    page_evidence = _validate_src_pages()
    pdf_entries = [x for x in rendered["inventory"] if x["source"].lower().endswith(".pdf")]
    manual_regions = [x for x in pdf_entries if x.get("extraction_status") == "not_separately_detected"]
    print(f"Prepared {len(fixture['tables'])} source tables across five documents.")
    print(f"Rendered {len(pdf_entries)} selected PDF fixture pages/entries.")
    print(f"Recorded {len(manual_regions)} visual/manual region(s) with separate extraction missing.")
    print(f"Inventory: {rendered['inventory_path'].relative_to(ROOT)}")
    print(f"HWP source cells: {rendered['hwp_path'].relative_to(ROOT)}")
    print(f"Validated {len(page_evidence)} PDF evaluation src references.")
    for case in page_evidence:
        pages = ", ".join(
            f"{item['document'][:2]} file p.{item['file_page']} / {item['page_count']}"
            for item in case["verified_file_pages"]
        )
        print(f"{case['set']}#{case['item']} src={case['src_only']!r}: {pages}")


if __name__ == "__main__":
    main()
