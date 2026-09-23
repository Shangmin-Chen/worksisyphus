"""Shared helper utilities and argument builders for CLI commands."""

from __future__ import annotations

import argparse
import io
import sys
from datetime import date
from pathlib import Path

from ....core.domain.models import CompilerConfig, CourseworkMode, Selection
from ....core.use_cases.application import list_applications, parse_app_folder


def read_stdin_text() -> str:
    """Read all of stdin as UTF-8, independent of the process locale.

    Plain ``sys.stdin.read()`` decodes using the locale's preferred encoding, so a JD pasted
    with non-ASCII text (curly quotes, accented names) could decode differently on different
    machines. Reading the underlying binary buffer through an explicit UTF-8 TextIOWrapper pins
    the encoding to match the file-path branch.
    """
    stdin = sys.stdin
    buffer = getattr(stdin, "buffer", None)
    if buffer is not None:
        return io.TextIOWrapper(buffer, encoding="utf-8").read()
    return stdin.read()


class InputReader:
    """Reads plan/JD text from a path, or from stdin for '-'.

    stdin can only be read once per process: a second read returns "". Threading every
    read through one object makes the second '-' impossible to reach rather than merely
    discouraged, so a future option that accepts '-' inherits the guard for free.
    """

    def __init__(self) -> None:
        self._stdin_option: str | None = None

    def read(self, arg: str, option: str) -> str:
        if arg != "-":
            return Path(arg).read_text(encoding="utf-8")
        if self._stdin_option is not None:
            raise ValueError(
                f"--{option} cannot also read stdin: --{self._stdin_option} already consumed it, "
                f"and a second read returns empty text. Pass --{option} a file path instead."
            )
        self._stdin_option = option
        return read_stdin_text()


def describe_selection(selection: Selection) -> str:
    """Format resolved plan selection into readable summary text."""
    lines = [f"plan OK: {selection.name}"]
    for label, picks in (("experiences", selection.experiences), ("projects", selection.projects)):
        lines.append(f"{label} ({len(picks)}):")
        lines += [f"  {pick.id}: {', '.join(pick.bullets)}" for pick in picks]
    lines.append("skills: " + ", ".join(f"{group} ({len(items)})" for group, items in selection.skills.items()))
    return "\n".join(lines)


def latest_application_pdf(applications_dir: Path | None = None) -> Path | None:
    """The most recent delivered resume. Applications are the only place a delivered PDF lives."""
    from worksisyphus.application import APPLICATIONS_DIR

    resolved_dir = applications_dir if applications_dir is not None else APPLICATIONS_DIR
    apps = list_applications(applications_dir=resolved_dir)
    if not apps:
        return None
    names = {app["folder"] for app in apps}

    def recency(app: dict[str, str]) -> tuple[int, int]:
        date_str, _, ordinal = parse_app_folder(app["folder"], siblings=names)
        try:
            day = date.fromisoformat(date_str).toordinal()
        except ValueError:
            day = 0
        return (day, ordinal or 0)

    newest = max(apps, key=recency)
    return resolved_dir / newest["folder"] / "Simon_Chen_Resume.pdf"


_latest_application_pdf = latest_application_pdf


def fit_column(value: object, width: int) -> str:
    """Keep table columns aligned while preserving the full application identifier."""
    text = str(value)
    return text if len(text) <= width else f"{text[: width - 1]}…"


def add_compiler_config_flags(parser: argparse.ArgumentParser) -> None:
    """Add layout and density configuration flags to a command parser."""
    parser.add_argument(
        "--include-gpa",
        action="store_true",
        help="Include GPA in the education section if present in the profile (default: False).",
    )
    parser.add_argument(
        "--compact-skills",
        action="store_true",
        help="Format technical skills into a single inline paragraph.",
    )
    parser.add_argument(
        "--coursework",
        choices=["full", "condensed", "none"],
        default="full",
        help="Coursework density rendering mode (default: full).",
    )
    parser.add_argument(
        "--density-ladder",
        action="store_true",
        help="Progressively compact coursework and skills before trimming content to fit one page.",
    )


def build_compiler_config(args: argparse.Namespace) -> CompilerConfig:
    """Instantiate a CompilerConfig dataclass from parsed CLI flags."""
    return CompilerConfig(
        include_gpa=getattr(args, "include_gpa", False),
        compact_skills=getattr(args, "compact_skills", False),
        coursework_mode=CourseworkMode(getattr(args, "coursework", "full")),
        enable_density_ladder=getattr(args, "density_ladder", False),
    )
