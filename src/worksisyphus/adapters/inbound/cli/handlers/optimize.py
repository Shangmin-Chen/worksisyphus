"""Optimize subcommand handler: knapsack plan optimizer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .....core.use_cases.optimizer import format_optimization_report, optimize_plan
from .. import commands
from ..helpers import InputReader


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "optimize", help="Combinatorially search and find the highest-scoring plan for a JD."
    )
    parser.add_argument("--jd", required=True, help="Job description text file or - for stdin.")
    parser.add_argument(
        "--role",
        default="software_engineer",
        help="Target role name for rubric evaluation.",
    )
    parser.add_argument("--output", default=None, help="Optional plan JSON file path to write winning plan to.")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace, read_input: InputReader) -> int:
    profile = commands.load_profile()
    jd_text = read_input.read(args.jd, "jd")
    best_plan, best_eval, results = optimize_plan(profile, jd_text, role_name=args.role)
    print(format_optimization_report(best_plan, best_eval, results))
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(best_plan, indent=2) + "\n", encoding="utf-8")
        print(f"\nOptimal plan written to: {out_path}")
    return 0
