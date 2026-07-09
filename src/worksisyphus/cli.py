"""Tiny CLI: `worksisyphus compile` and `worksisyphus tailor --jd <file|->`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import build_canonical, tailor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worksisyphus", description="Resume compiler.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("compile", help="Rebuild the canonical full resume (no AI).")
    tailor_cmd = sub.add_parser("tailor", help="Generate a one-page resume tailored to a job description.")
    tailor_cmd.add_argument("--jd", required=True, help="Path to a job description text file, or - for stdin.")
    args = parser.parse_args(argv)

    try:
        if args.command == "compile":
            build_canonical(log=print)
        else:
            jd_text = sys.stdin.read() if args.jd == "-" else Path(args.jd).read_text(encoding="utf-8")
            tailor(jd_text, log=print)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
