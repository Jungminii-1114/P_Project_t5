"""Source adapters. No language-model clients are imported or invoked."""

import json
import re

from .ir import Cell, Table, table_id
from .table_ir import infer_structure


def hwp_table(cells_json, source, locator, page, ordinal, config):
    raw = json.loads(cells_json)
    if not raw:
        return None
    cells = []
    for value in raw:
        text = re.sub(config.hwp_marker_pattern, " ", value.get("text") or "")
        text = " ".join(text.split()).replace("|", "/")
        if text == config.image_marker:
            text = ""
        cells.append(Cell(value["row"], value["col"], max(value.get("rowspan", 1), 1),
                          max(value.get("colspan", 1), 1), text))
    return infer_structure(Table(table_id(source, locator, ordinal), source, locator, page,
        max(c.row+c.rowspan for c in cells), max(c.col+c.colspan for c in cells),
        cells, origin="hwp_cells"), config)


def _boundaries(values, tolerance):
    out = []
    for value in sorted(values):
        if not out or value-out[-1] > tolerance:
            out.append(value)
    return out


def _clean(text):
    return " ".join((text or "").split())


def pdf_table(page, found, rows, source, number, ordinal, config):
    locator = {"type": "page", "value": number}
    diagnostics = {}
    cells = []
    try:
        if found is None or not found.cells:
            raise ValueError("missing_cell_geometry")
        boxes = found.cells
        xs = _boundaries([x for b in boxes for x in (b[0], b[2])], config.ir_coord_tolerance)
        ys = _boundaries([y for b in boxes for y in (b[1], b[3])], config.ir_coord_tolerance)
        # Access both library axes as part of the adapter contract.
        diagnostics["library_rows"] = len(found.rows)
        diagnostics["library_columns"] = len(found.columns)
        differences = []
        for bbox in boxes:
            x0, top, x1, bottom = bbox
            c0, c1 = [min(range(len(xs)), key=lambda j: abs(xs[j]-x)) for x in (x0, x1)]
            r0, r1 = [min(range(len(ys)), key=lambda j: abs(ys[j]-y)) for y in (top, bottom)]
            text = _clean(page.crop(bbox).extract_text())
            cells.append(Cell(r0, c0, r1-r0, c1-c0, text))
            # extract_tables() follows found.rows cell anchors; compare by bbox,
            # not by inferred grid indices (which may introduce extra boundaries).
            old = ""
            for ri, library_row in enumerate(found.rows):
                for ci, box in enumerate(library_row.cells):
                    if box == bbox and ri < len(rows) and ci < len(rows[ri]):
                        old = _clean(rows[ri][ci])
            if old != text:
                differences.append({"row": r0, "col": c0, "legacy": old, "crop": text})
        diagnostics["cell_text_comparison"] = {"cells": len(cells), "differences": differences,
                                                "matches": len(cells)-len(differences)}
        table = Table(table_id(source, locator, ordinal), source, locator, number,
            len(ys)-1, len(xs)-1, cells, origin="pdf_cells", diagnostics=diagnostics)
    except (ValueError, TypeError, IndexError) as error:
        diagnostics["fallback_reason"] = str(error)
        table = Table(table_id(source, locator, ordinal), source, locator, number,
            len(rows), max((len(r) for r in rows), default=0),
            [Cell(r, c, text=_clean(value)) for r, row in enumerate(rows)
             for c, value in enumerate(row)], origin="pdf_fallback", diagnostics=diagnostics)
    return infer_structure(table, config)
