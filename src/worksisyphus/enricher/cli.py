from __future__ import annotations

import argparse
from pathlib import Path

from worksisyphus.enricher.pipeline import EnrichResult, enrich_latest

DEFAULT_NORMALIZER_DIR = Path(".worksisyphus") / "normalizer"
DEFAULT_OUTPUT_DIR = Path(".worksisyphus") / "enricher"
DEFAULT_DB_PATH = Path(".worksisyphus") / "catalog.sqlite3"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="worksisyphus-enrich",
        description="Phase 3 job enrichment.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="enrich latest normalized jobs with detail-page data",
    )
    run_parser.add_argument(
        "--normalizer-dir",
        type=Path,
        default=DEFAULT_NORMALIZER_DIR,
        help=f"phase 2 output directory; default: {DEFAULT_NORMALIZER_DIR}",
    )
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"phase 3 output directory; default: {DEFAULT_OUTPUT_DIR}",
    )
    run_parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"catalog SQLite path; default: {DEFAULT_DB_PATH}",
    )
    run_parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="maximum missing jobs to enrich this run; use 0 for all",
    )
    run_parser.add_argument(
        "--refresh",
        action="store_true",
        help="refetch jobs even if an enrichment already exists",
    )
    run_parser.add_argument(
        "--delay",
        type=float,
        default=0.25,
        help="seconds to wait between requests; default: 0.25",
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        limit = None if args.limit == 0 else args.limit
        result = enrich_latest(
            normalizer_dir=args.normalizer_dir.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
            db_path=args.db.expanduser().resolve(),
            limit=limit,
            refresh=args.refresh,
            delay_seconds=args.delay,
        )
        _print_result(result)
        return 0

    return 2


def _print_result(result: EnrichResult) -> None:
    print(
        "\n".join(
            [
                f"enriched_at: {result.observed_at}",
                f"input_file: {result.input_file}",
                f"db_path: {result.db_path}",
                f"attempted_count: {result.attempted_count}",
                f"enriched_count: {result.enriched_count}",
                f"skipped_count: {result.skipped_count}",
                f"failed_count: {result.failed_count}",
                f"latest_json: {result.latest_json}",
                f"latest_jsonl: {result.latest_jsonl}",
                f"run_summary: {result.run_summary}",
            ]
        )
    )
