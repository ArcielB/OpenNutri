#!/usr/bin/env python3
"""Build versioned OpenNutri Core dataset artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from opennutri_core import DEFAULT_OUTPUT_DIR, DEFAULT_SOURCE_DIR, build_fndds_release


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the OpenNutri Core FNDDS release")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the exact output directory after a successful temporary build.",
    )
    parser.add_argument(
        "--allow-nonofficial-counts",
        action="store_true",
        help="Skip exact official-release count assertions (intended for fixtures only).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = build_fndds_release(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
        strict_official=not args.allow_nonofficial_counts,
    )
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir.resolve()),
                "status": report["status"],
                "measured": report["measured"],
                "output_rows": report["output_rows"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
