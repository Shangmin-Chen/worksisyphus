from __future__ import annotations

import argparse
from pathlib import Path

from worksisyphus.aggregator.config import SOURCES
from worksisyphus.normalizer.pipeline import NormalizeResult, normalize_latest

DEFAULT_AGGREGATOR_DIR = Path(".worksisyphus") / "aggregator"
DEFAULT_OUTPUT_DIR = Path(".worksisyphus") / "normalizer"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="worksisyphus-normalize",
        description="Phase 2 job normalization.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="normalize the latest phase 1 aggregate artifact",
    )
    run_parser.add_argument(
        "--source",
        choices=sorted(SOURCES),
        default="jobright_ai_2026_software_engineer_new_grad",
        help="configured source to normalize",
    )
    run_parser.add_argument(
        "--aggregator-dir",
        type=Path,
        default=DEFAULT_AGGREGATOR_DIR,
        help=f"phase 1 output directory; default: {DEFAULT_AGGREGATOR_DIR}",
    )
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"phase 2 output directory; default: {DEFAULT_OUTPUT_DIR}",
    )

    args = parser.parse_args(argv)

    if args.command == "run":
        result = normalize_latest(
            aggregator_dir=args.aggregator_dir.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
            source_slug=args.source,
        )
        _print_result(result)
        return 0

    return 2


def _print_result(result: NormalizeResult) -> None:
    print(
        "\n".join(
            [
                f"source: {result.source}",
                f"normalized_at: {result.observed_at}",
                f"input_file: {result.input_file}",
                f"total_jobs: {result.total_jobs}",
                f"needs_review_count: {result.needs_review_count}",
                f"latest_json: {result.latest_json}",
                f"latest_jsonl: {result.latest_jsonl}",
                f"run_summary: {result.run_summary}",
            ]
        )
    )
