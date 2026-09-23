"""Tailor subcommand handler: preview builds into tex_files/."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .....core.domain.models import CompilerConfig
from .. import commands
from ..helpers import InputReader, add_compiler_config_flags, build_compiler_config


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "tailor",
        help="Preview build into tex_files/ (never delivers; use 'apply' for job applications).",
    )
    parser.add_argument("--plan", required=True, help="Path to a plan JSON file, or - for stdin.")
    parser.add_argument("--output", default=None, help="Output directory (default: tex_files/).")
    add_compiler_config_flags(parser)
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace, read_input: InputReader) -> int:
    config = build_compiler_config(args)
    tailor_kwargs: dict[str, Any] = {"log": print}
    if config != CompilerConfig():
        tailor_kwargs["config"] = config
    commands.tailor(
        read_input.read(args.plan, "plan"),
        pdf_dir=Path(args.output) if args.output else commands.PREVIEW_DIR,
        **tailor_kwargs,
    )
    print("Preview build only - run `worksisyphus apply` to produce a delivered resume.")
    return 0
