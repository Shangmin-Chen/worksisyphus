"""Tiny CLI for compiling, tailoring, archiving, and tracking applications."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .archive import STATUSES, archive_application, list_applications, update_application_status
from .pipeline import PDF_DIR, build_canonical, tailor
from .plan import parse_plan
from .profile import load_profile, profile_index
from .selection import Selection


def _read_plan(arg: str) -> str:
    """Return plan text from a path or - for stdin."""
    return sys.stdin.read() if arg == "-" else Path(arg).read_text(encoding="utf-8")


def _describe(selection: Selection) -> str:
    lines = [f"plan OK: {selection.name}"]
    for label, picks in (("experiences", selection.experiences), ("projects", selection.projects)):
        lines.append(f"{label} ({len(picks)}):")
        lines += [f"  {pick.id}: {', '.join(pick.bullets)}" for pick in picks]
    lines.append("skills: " + ", ".join(f"{group} ({len(items)})" for group, items in selection.skills.items()))
    return "\n".join(lines)


def _fit_column(value: object, width: int) -> str:
    """Keep table columns aligned while preserving the full application identifier."""
    text = str(value)
    return text if len(text) <= width else f"{text[:width - 1]}…"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worksisyphus", description="Resume compiler.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("compile", help="Rebuild the canonical full resume.")
    sub.add_parser("index", help="Print every slug a plan file can reference.")
    tailor_cmd = sub.add_parser("tailor", help="Compile a one-page resume from a plan file of slugs.")
    tailor_cmd.add_argument("--plan", required=True, help="Path to a plan JSON file, or - for stdin.")
    validate_cmd = sub.add_parser("validate", help="Parse a plan and print the resolved selection; no LaTeX involved.")
    validate_cmd.add_argument("--plan", required=True, help="Path to a plan JSON file, or - for stdin.")
    archive_cmd = sub.add_parser("archive", help="Freeze a compiled application into applications/<date>_<name>/.")
    archive_cmd.add_argument("--plan", required=True, help="Path to the plan JSON file that built the resume.")
    archive_cmd.add_argument("--company", required=True, help="Company applied to.")
    archive_cmd.add_argument("--jd", required=True, help="Path to the job description text file, or - for stdin.")
    archive_cmd.add_argument("--role", default="", help="Role title, if known.")
    archive_cmd.add_argument("--url", default="", help="Posting URL, if any.")
    sub.add_parser("status", help="List all archived applications and their current statuses.")
    update_cmd = sub.add_parser("update-status", help="Update the status of an archived application.")
    update_cmd.add_argument(
        "--app",
        required=True,
        help="Exact application folder name or unique plan stem (e.g. dirac_full-stack-engineer).",
    )
    update_cmd.add_argument("--status", required=True, choices=STATUSES, help="New status value.")
    args = parser.parse_args(argv)

    try:
        if args.command == "compile":
            build_canonical(log=print)
        elif args.command == "index":
            print(profile_index(load_profile()))
        elif args.command == "validate":
            print(_describe(parse_plan(_read_plan(args.plan), load_profile())))
        elif args.command == "archive":
            plan_path = Path(args.plan)
            selection = parse_plan(plan_path.read_text(encoding="utf-8"), load_profile())
            jd_text = _read_plan(args.jd)
            folder = archive_application(
                plan_path, PDF_DIR / f"{selection.name}.pdf", jd_text,
                company=args.company, role=args.role, source_url=args.url,
            )
            print(f"Archived {folder}")
        elif args.command == "status":
            apps = list_applications()
            if not apps:
                print("No archived applications found.")
            else:
                header = f"{'Date':<12} {'Company':<20} {'Role':<32} {'Status':<15} Application"
                print(header)
                print("-" * len(header))
                for app in apps:
                    print(
                        f"{_fit_column(app.get('date', ''), 12):<12} "
                        f"{_fit_column(app.get('company', ''), 20):<20} "
                        f"{_fit_column(app.get('role', ''), 32):<32} "
                        f"{_fit_column(app.get('status', ''), 15):<15} {app.get('folder', '')}"
                    )
        elif args.command == "update-status":
            folder, old_status, new_status = update_application_status(args.app, args.status)
            print(f"Updated {folder.name}: {old_status} -> {new_status}")
        else:
            tailor(_read_plan(args.plan), log=print)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
