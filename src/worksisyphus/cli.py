"""Tiny CLI: `worksisyphus compile | tailor --plan <file|-> | validate --plan <file|-> | index`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import build_canonical, tailor
from .plan import parse_plan
from .profile import load_profile, profile_index
from .selection import Selection


def _read_plan(arg: str) -> tuple[str, str]:
    """Return (plan_text, default_name) from a path or - for stdin."""
    if arg == "-":
        return sys.stdin.read(), ""
    path = Path(arg)
    return path.read_text(encoding="utf-8"), path.stem


def _describe(selection: Selection) -> str:
    lines = [f"plan OK: {selection.name}"]
    for label, picks in (("experiences", selection.experiences), ("projects", selection.projects)):
        lines.append(f"{label} ({len(picks)}):")
        lines += [f"  {pick.id}: {', '.join(pick.bullets)}" for pick in picks]
    lines.append("skills: " + ", ".join(f"{group} ({len(items)})" for group, items in selection.skills.items()))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worksisyphus", description="Resume compiler.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("compile", help="Rebuild the canonical full resume.")
    sub.add_parser("index", help="Print every slug a plan file can reference.")
    tailor_cmd = sub.add_parser("tailor", help="Compile a one-page resume from a plan file of slugs.")
    tailor_cmd.add_argument("--plan", required=True, help="Path to a plan JSON file, or - for stdin.")
    validate_cmd = sub.add_parser("validate", help="Parse a plan and print the resolved selection; no LaTeX involved.")
    validate_cmd.add_argument("--plan", required=True, help="Path to a plan JSON file, or - for stdin.")
    args = parser.parse_args(argv)

    try:
        if args.command == "compile":
            build_canonical(log=print)
        elif args.command == "index":
            print(profile_index(load_profile()))
        elif args.command == "validate":
            plan_text, default_name = _read_plan(args.plan)
            print(_describe(parse_plan(plan_text, load_profile(), default_name)))
        else:
            plan_text, default_name = _read_plan(args.plan)
            tailor(plan_text, default_name=default_name, log=print)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
