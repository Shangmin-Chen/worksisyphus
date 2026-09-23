"""Command-line interface router for worksisyphus resume compiler and application manager."""

from __future__ import annotations

import argparse
import sys

from ....core.domain.models import CompilerConfig, CourseworkMode, Selection, profile_index
from ....core.domain.plan import parse_plan
from ....core.use_cases.application import (
    STATUSES,
    list_applications,
    parse_app_folder,
    slugify,
    update_application_status,
)
from ....core.use_cases.application import apply as apply_app
from ....core.use_cases.pipeline import PREVIEW_DIR, build_canonical, tailor
from ...outbound.filesystem.profile_loader import load_profile
from .handlers import (
    apply as apply_handler,
)
from .handlers import (
    backfill as backfill_handler,
)
from .handlers import (
    compile_cmd as compile_handler,
)
from .handlers import (
    db as db_handler,
)
from .handlers import (
    evaluate as evaluate_handler,
)
from .handlers import (
    index as index_handler,
)
from .handlers import (
    optimize as optimize_handler,
)
from .handlers import (
    status as status_handler,
)
from .handlers import (
    tailor as tailor_handler,
)
from .handlers import (
    validate as validate_handler,
)
from .helpers import (
    InputReader,
    _latest_application_pdf,
    build_compiler_config,
    describe_selection,
    fit_column,
    latest_application_pdf,
    read_stdin_text,
)

__all__ = [
    "PREVIEW_DIR",
    "STATUSES",
    "CompilerConfig",
    "CourseworkMode",
    "InputReader",
    "Selection",
    "_latest_application_pdf",
    "apply_app",
    "build_canonical",
    "build_compiler_config",
    "build_parser",
    "describe_selection",
    "fit_column",
    "latest_application_pdf",
    "list_applications",
    "load_profile",
    "main",
    "parse_app_folder",
    "parse_plan",
    "profile_index",
    "read_stdin_text",
    "slugify",
    "tailor",
    "update_application_status",
]


def build_parser() -> argparse.ArgumentParser:
    """Construct top-level argument parser with all registered subcommand modules."""
    parser = argparse.ArgumentParser(
        prog="worksisyphus",
        description="Simon Chen's resume compiler: hand-written slug plans in, one-page LaTeX PDFs out.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    apply_handler.register(sub)
    tailor_handler.register(sub)
    compile_handler.register(sub)
    validate_handler.register(sub)
    index_handler.register(sub)
    status_handler.register(sub)
    backfill_handler.register(sub)
    db_handler.register(sub)
    evaluate_handler.register(sub)
    optimize_handler.register(sub)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    read_input = InputReader()

    try:
        handler = getattr(args, "handler", None)
        if handler is None:
            raise ValueError(f"Unknown command: {args.command}")
        return handler(args, read_input)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
