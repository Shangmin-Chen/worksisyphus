from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from worksisyphus.aggregator.config import SOURCES
from worksisyphus.aggregator.pipeline import PollResult, poll_once

DEFAULT_DATA_DIR = Path(".worksisyphus") / "aggregator"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="worksisyphus-aggregate",
        description="Phase 1 job listing aggregator.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    poll_parser = subparsers.add_parser("poll", help="poll the configured source once")
    _add_common_args(poll_parser)

    watch_parser = subparsers.add_parser("watch", help="poll forever on an interval")
    _add_common_args(watch_parser)
    watch_parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="seconds between polls; default: 300",
    )

    args = parser.parse_args(argv)

    source = SOURCES[args.source]
    data_dir = args.data_dir.expanduser().resolve()

    if args.command == "poll":
        result = poll_once(data_dir=data_dir, source=source)
        _print_result(result)
        return 0

    if args.command == "watch":
        while True:
            try:
                result = poll_once(data_dir=data_dir, source=source)
                _print_result(result)
            except KeyboardInterrupt:
                return 130
            except Exception as exc:  # pragma: no cover - keeps listener alive.
                print(f"poll failed: {exc}", file=sys.stderr)
            time.sleep(args.interval)

    return 2


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        choices=sorted(SOURCES),
        default="jobright_ai_2026_software_engineer_new_grad",
        help="configured source to poll",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"output directory; default: {DEFAULT_DATA_DIR}",
    )


def _print_result(result: PollResult) -> None:
    print(
        "\n".join(
            [
                f"source: {result.source}",
                f"commit: {result.commit}",
                f"observed_at: {result.observed_at}",
                f"total_listings: {result.total_listings}",
                f"new_count: {result.new_count}",
                f"removed_count: {result.removed_count}",
                f"unchanged_commit: {str(result.unchanged_commit).lower()}",
                f"latest_json: {result.latest_json}",
                f"latest_jsonl: {result.latest_jsonl}",
                f"run_summary: {result.run_summary}",
                f"state_file: {result.state_file}",
            ]
        )
    )
