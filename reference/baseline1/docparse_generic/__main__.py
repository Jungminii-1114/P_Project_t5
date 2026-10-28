"""Parse local documents using neutral settings or a selected profile."""

import argparse
from pathlib import Path

from . import run_all
from .config import load_profile
from .serialization import write_outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Local files, directories, or glob patterns")
    parser.add_argument("--profile", default="neutral", help="Profile module name or JSON path")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    config = load_profile(args.profile)
    results = run_all(args.paths, config)
    manifest = write_outputs(results, args.paths, args.out, config)
    print(f"Completed: {manifest['counts']['contextual_chunks']} contextual chunks")


if __name__ == "__main__":
    main()
