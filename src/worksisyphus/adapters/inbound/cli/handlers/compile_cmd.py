"""Compile subcommand handler: canonical 3-page database view."""

from __future__ import annotations

import argparse

from .....core.use_cases.pipeline import build_canonical
from ..helpers import InputReader


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "compile",
        help="Compile canonical 3-page database view from profile.json (internal reference only).",
    )
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace, read_input: InputReader) -> int:
    build_canonical(log=print)
    print("Canonical resume is the database view for reference only; never send to employers.")
    return 0
