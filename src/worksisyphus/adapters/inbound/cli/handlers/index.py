"""Index subcommand handler: list all selectable content slugs."""

from __future__ import annotations

import argparse

from .. import commands
from ..helpers import InputReader


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "index",
        help="List all selectable slugs and full bullet text from profile.json.",
    )
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace, read_input: InputReader) -> int:
    print(commands.profile_index(commands.load_profile()))
    return 0
