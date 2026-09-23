"""Validate subcommand handler: parse and verify plan without compiling."""

from __future__ import annotations

import argparse

from .. import commands
from ..helpers import InputReader, describe_selection


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "validate",
        help="Parse a plan and print the resolved selection; no LaTeX involved.",
    )
    parser.add_argument("--plan", required=True, help="Path to a plan JSON file, or - for stdin.")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace, read_input: InputReader) -> int:
    profile = commands.load_profile()
    selection = commands.parse_plan(read_input.read(args.plan, "plan"), profile)
    print(describe_selection(selection))
    return 0
