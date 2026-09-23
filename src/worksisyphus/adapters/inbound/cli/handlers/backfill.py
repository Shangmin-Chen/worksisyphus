"""Backfill evaluations subcommand handler."""

from __future__ import annotations

import argparse

from .....core.use_cases.application import backfill_evaluations
from ..helpers import InputReader


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "backfill-evals",
        help="Score applications that predate evaluation recording.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-score applications that already have an evaluation.",
    )
    # Legacy flags accepted as no-ops
    parser.add_argument("--no-sync", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--allow-branch", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-git-check", action="store_true", help=argparse.SUPPRESS)
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace, read_input: InputReader) -> int:
    scored = backfill_evaluations(overwrite=args.overwrite, log=print)
    if not scored:
        print("No applications needed scoring.")
    else:
        print(f"Scored {len(scored)} application(s).")
    return 0
