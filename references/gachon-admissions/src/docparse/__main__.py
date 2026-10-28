"""Parse local documents using neutral settings or a selected profile."""

import argparse
from dataclasses import replace
from pathlib import Path

from . import run_all
from .config import load_profile
from .serialization import write_outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Local files, directories, or glob patterns")
    parser.add_argument("--profile", default="neutral", help="Profile module name or JSON path")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--index-render", choices=("baseline1", "header_records"), default="baseline1")
    parser.add_argument("--llm-render", choices=("baseline1", "html_full", "header_records"), default="baseline1")
    parser.add_argument("--extract-table-ir", action="store_true")
    args = parser.parse_args()
    config = replace(load_profile(args.profile), index_render=args.index_render,
                     llm_render=args.llm_render, extract_table_ir=args.extract_table_ir)
    results = run_all(args.paths, config)
    manifest = write_outputs(results, args.paths, args.out, config)
    print(f"Completed: {manifest['counts']['contextual_chunks']} contextual chunks")


if __name__ == "__main__":
    main()
