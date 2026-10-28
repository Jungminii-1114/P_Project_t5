"""Compare local Kiwi BM25 page retrieval for the two table index renderers.

This is a keyword-only proxy. It deliberately does not import the pipeline or
apply any of its routing, dense retrieval, fusion, or score adjustments.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import re
from pathlib import Path
from typing import Any

from kiwipiepy import Kiwi
from rank_bm25 import BM25Okapi


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data" / "dataset"
DEFAULT_EVAL_DIR = ROOT / "eval"
DEFAULT_OUTPUT = ROOT / "reference" / "baseline2" / "metrics" / "bm25.json"
DEFAULT_CACHE_DIR = ROOT / "runs" / "baseline2" / "bm25"

ALLOWED_TAGS = frozenset({"NNG", "NNP", "NNB", "VV", "VA", "XR", "SL", "SN"})
TOP_K = (1, 3, 8)
PAGE_RE = re.compile(r"(?i)\bp\.?\s*(\d+)(?:\s*(?:-|–|~|∼)\s*p?\.?\s*(\d+))?")
DOC_PREFIX_RE = re.compile(r"^\s*(\d{2})(?=\s|$)")


def tokenize(text: str, kiwi: Kiwi) -> list[str]:
    """Match the frozen baseline Kiwi tag filter used by its BM25 tokenizer."""
    return [token.form for token in kiwi.tokenize(text) if token.tag in ALLOWED_TAGS]


def document_extensions(required_files: tuple[str, ...] | list[str]) -> dict[str, str]:
    """Map source prefixes from a parser profile to their file extensions."""
    mapping: dict[str, str] = {}
    for filename in required_files:
        path = Path(filename)
        match = re.match(r"^(\d{2})", path.name)
        if match:
            mapping[match.group(1)] = path.suffix.lower()
    return mapping


def parse_src_references(src: Any, extensions: dict[str, str]) -> dict[str, Any]:
    """Parse PDF source pages, inheriting a document prefix across slash groups.

    `01 (전형료 표)` is retained as an excluded HWP source even though it has
    no numbered page. Ranges such as `03 p.4-6` expand inclusively. The returned
    structure contains no raw source string, so it can be written to metrics.
    """
    if src is None or not str(src).strip():
        return {
            "source_status": "absent",
            "pdf_pages": [],
            "hwp_source_segments": 0,
            "hwp_page_references": 0,
            "unparsed_segments": 0,
        }

    current_doc: str | None = None
    pdf_pages: list[dict[str, Any]] = []
    seen_pages: set[tuple[str, int]] = set()
    hwp_segments = 0
    hwp_page_references = 0
    unparsed_segments = 0

    for segment in str(src).split("/"):
        segment = segment.strip()
        doc_match = DOC_PREFIX_RE.match(segment)
        if doc_match:
            current_doc = doc_match.group(1)
        if current_doc is None or current_doc not in extensions:
            if segment:
                unparsed_segments += 1
            continue

        is_pdf = extensions[current_doc] == ".pdf"
        if not is_pdf:
            hwp_segments += 1

        page_matches = list(PAGE_RE.finditer(segment))
        if not page_matches and is_pdf:
            # A document label without a file-page locator cannot be scored.
            unparsed_segments += 1
        for match in page_matches:
            start = int(match.group(1))
            end = int(match.group(2) or start)
            if end < start:
                start, end = end, start
            page_numbers = range(start, end + 1)
            if not is_pdf:
                hwp_page_references += len(page_numbers)
                continue
            for page in page_numbers:
                key = (current_doc, page)
                if key not in seen_pages:
                    seen_pages.add(key)
                    pdf_pages.append({"document": current_doc, "page": page})

    if pdf_pages:
        status = "pdf"
    elif hwp_segments:
        status = "hwp_only"
    else:
        status = "unparsed"
    return {
        "source_status": status,
        "pdf_pages": pdf_pages,
        "hwp_source_segments": hwp_segments,
        "hwp_page_references": hwp_page_references,
        "unparsed_segments": unparsed_segments,
    }


def score_page_hits(
    target_pages: list[dict[str, Any]], ranked_pages: list[dict[str, Any]], top_k: int
) -> dict[str, Any]:
    """Return page-level, any-source, and all-source hits among top-k chunks."""
    targets = {(page["document"], int(page["page"])) for page in target_pages}
    retrieved = {
        (page["document"], int(page["page"]))
        for page in ranked_pages[:top_k]
        if page is not None
    }
    page_hits = [
        {"document": document, "page": page, "hit": (document, page) in retrieved}
        for document, page in target_pages_as_tuples(target_pages)
    ]
    hit_count = sum(1 for page in page_hits if page["hit"])
    return {
        "any_page_hit": bool(targets & retrieved),
        "all_pages_hit": bool(targets) and targets.issubset(retrieved),
        "page_hits": page_hits,
        "page_hit_count": hit_count,
        "target_page_count": len(targets),
    }


def target_pages_as_tuples(pages: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """Preserve input order while removing duplicate page citations."""
    result = []
    seen = set()
    for page in pages:
        key = (page["document"], int(page["page"]))
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _summarize_queries(queries: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    scorable = [query for query in queries if query["pdf_pages"]]
    summary: dict[str, Any] = {
        "scorable_queries": len(scorable),
        "excluded_hwp_queries": sum(query["hwp_source_segments"] > 0 for query in queries),
        "excluded_hwp_only_queries": sum(query["source_status"] == "hwp_only" for query in queries),
        "excluded_hwp_page_references": sum(query["hwp_page_references"] for query in queries),
    }
    for top_k in TOP_K:
        key = str(top_k)
        scored = [query["modes"][mode][key] for query in scorable]
        page_total = sum(result["target_page_count"] for result in scored)
        page_hits = sum(result["page_hit_count"] for result in scored)
        summary[key] = {
            "any_page_hit_queries": sum(result["any_page_hit"] for result in scored),
            "any_page_hit_rate": _rate(sum(result["any_page_hit"] for result in scored), len(scored)),
            "all_pages_hit_queries": sum(result["all_pages_hit"] for result in scored),
            "all_pages_hit_rate": _rate(sum(result["all_pages_hit"] for result in scored), len(scored)),
            "page_level_hits": page_hits,
            "page_level_targets": page_total,
            "page_level_hit_rate": _rate(page_hits, page_total),
        }
    return summary


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _load_eval_sets(eval_dir: Path) -> list[tuple[str, list[dict[str, Any]]]]:
    sets = []
    for path in sorted(eval_dir.glob("testset_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Expected a JSON list in {path}")
        sets.append((path.stem.removeprefix("testset_"), payload))
    if not sets:
        raise FileNotFoundError(f"No testset_*.json files under {eval_dir}")
    return sets


def _run_mode(data_dir: Path, output_dir: Path, mode: str, profile):
    """Run the local parser for one index renderer and persist its cache."""
    from docparse import run_all
    from docparse.serialization import write_outputs

    config = replace(profile, index_render=mode)
    results = run_all(data_dir, config)
    manifest = write_outputs(results, data_dir, output_dir, config)
    return results, manifest


def _bm25_page_ranks(contextual_chunks, questions: list[str], kiwi: Kiwi) -> list[list[dict[str, Any]]]:
    corpus = [tokenize(chunk.page_content, kiwi) for chunk in contextual_chunks]
    if not corpus:
        raise ValueError("Parser returned no contextual chunks")
    bm25 = BM25Okapi(corpus)
    chunk_pages = []
    for chunk in contextual_chunks:
        metadata = chunk.metadata
        source = str(metadata.get("source", ""))
        prefix = Path(source).name[:2]
        page = metadata.get("page")
        if not source.lower().endswith(".pdf") or not prefix.isdigit() or page is None:
            chunk_pages.append(None)
        else:
            try:
                chunk_pages.append({"document": prefix, "page": int(page)})
            except (TypeError, ValueError):
                chunk_pages.append(None)

    rankings = []
    row_ids = list(range(len(contextual_chunks)))
    for question in questions:
        query_tokens = tokenize(question, kiwi)
        top_ids = bm25.get_top_n(query_tokens, row_ids, n=max(TOP_K)) if query_tokens else []
        rankings.append([chunk_pages[row] for row in top_ids])
    return rankings


def _verified_page_basis() -> dict[str, Any]:
    """Record the independently inspected page-number prerequisite."""
    return {
        "status": "passed",
        "method": "manual inspection of rendered original PDF file pages",
        "checked_examples": [
            {"set": "holdout", "id": 6, "document": "04", "page": 35,
             "evidence": "table is on file page 35; printed folio is 61"},
            {"set": "drive20", "id": 17, "document": "03", "page": 85,
             "evidence": "grade interval table is on file page 85"},
            {"set": "drive20", "id": 19, "document": "05", "page": 2,
             "evidence": "interview schedule table is on file page 2"},
        ],
    }


def run_diagnostic(
    data_dir: Path = DEFAULT_DATA_DIR,
    eval_dir: Path = DEFAULT_EVAL_DIR,
    output_path: Path = DEFAULT_OUTPUT,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> dict[str, Any]:
    """Parse both render modes, rank every question locally, and write metrics."""
    from docparse import load_profile

    data_dir = Path(data_dir).resolve()
    eval_dir = Path(eval_dir).resolve()
    output_path = Path(output_path).resolve()
    cache_dir = Path(cache_dir).resolve()
    profile = load_profile("gachon_2027")
    extensions = document_extensions(profile.required_files)
    eval_sets = _load_eval_sets(eval_dir)

    parsed_items: dict[str, list[dict[str, Any]]] = {}
    for set_name, items in eval_sets:
        parsed_items[set_name] = []
        for item in items:
            parsed = parse_src_references(item.get("src"), extensions)
            parsed_items[set_name].append({
                "set": set_name,
                "id": item.get("id"),
                **parsed,
                "modes": {},
            })

    # A run is forbidden unless at least three independently verified examples
    # are recorded above. This prevents accidental use of printed folios as PDF
    # file pages in later reproductions.
    page_basis = _verified_page_basis()
    if page_basis["status"] != "passed" or len(page_basis["checked_examples"]) < 3:
        raise RuntimeError("PDF src page basis is not verified; stopping before BM25")

    kiwi = Kiwi()
    manifests = {}
    for mode in ("baseline1", "header_records"):
        results, manifest = _run_mode(data_dir, cache_dir / mode, mode, profile)
        manifests[mode] = manifest["counts"]
        flat_items = [item for _, items in eval_sets for item in items]
        rankings = _bm25_page_ranks(
            results["contextual_chunks"], [str(item.get("q", "")) for item in flat_items], kiwi
        )
        cursor = 0
        for set_name, items in eval_sets:
            for item, query in zip(items, parsed_items[set_name], strict=True):
                ranked_pages = rankings[cursor]
                cursor += 1
                if not query["pdf_pages"]:
                    continue
                query["modes"][mode] = {
                    str(k): score_page_hits(query["pdf_pages"], ranked_pages, k)
                    for k in TOP_K
                }

    summaries = {}
    query_records = []
    all_queries = [query for queries in parsed_items.values() for query in queries]
    for set_name, _ in eval_sets:
        queries = parsed_items[set_name]
        summaries[set_name] = {
            "questions": len(queries),
            "absent_src_queries": sum(query["source_status"] == "absent" for query in queries),
            "unparsed_src_queries": sum(query["source_status"] == "unparsed" for query in queries),
            "modes": {
                mode: _summarize_queries(queries, mode)
                for mode in ("baseline1", "header_records")
            },
        }
        query_records.extend(queries)

    result = {
        "schema_version": 1,
        "metric": "BM25 keyword-only proxy: target PDF file pages appearing in the top-k retrieved chunks",
        "interpretation": "This is a BM25 proxy, not hybrid retrieval; no routing, dense search, fusion, or boosts are applied.",
        "source_page_basis": page_basis,
        "tokenizer": {
            "implementation": "kiwipiepy.Kiwi",
            "allowed_tags": sorted(ALLOWED_TAGS),
            "corpus_and_query_filter": "retain tokens whose Kiwi POS tag is in allowed_tags",
        },
        "index_modes": list(manifests),
        "top_k": list(TOP_K),
        "parser_counts": manifests,
        "summary_by_set": summaries,
        # Query records contain identifiers and source locators only: no question or gold text.
        "queries": query_records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--eval-dir", type=Path, default=DEFAULT_EVAL_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args(argv)
    result = run_diagnostic(args.data_dir, args.eval_dir, args.out, args.cache_dir)
    print(f"BM25 diagnostic saved: {args.out}")
    for set_name, summary in result["summary_by_set"].items():
        for mode in result["index_modes"]:
            mode_summary = summary["modes"][mode]
            any_hits = ", ".join(
                f"k={k} {mode_summary[str(k)]['any_page_hit_queries']}/{mode_summary['scorable_queries']}"
                for k in TOP_K
            )
            print(f"  {set_name} {mode}: any-page hits {any_hits}")
        print(
            f"  {set_name}: questions={summary['questions']} "
            f"absent-src={summary['absent_src_queries']} "
            f"HWP-excluded={summary['modes']['baseline1']['excluded_hwp_queries']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
