"""Track subcommand handler: persist and manage job opportunities in the lead vault (Venue 1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .....core.use_cases.tracker import list_leads, track_lead
from ....outbound.ingestion.scratch_bridge import ScratchBridge
from ..helpers import InputReader, fit_column


def register_track(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "track",
        help="Track a job opportunity into the leads vault (Venue 1) without compiling a resume.",
    )
    parser.add_argument(
        "--company",
        default="",
        help="Company name (e.g. Stripe, Palantir).",
    )
    parser.add_argument(
        "--role",
        default="Software Engineer",
        help="Target role name (defaults to Software Engineer).",
    )
    parser.add_argument(
        "--url",
        default="",
        help="URL of the job posting.",
    )
    parser.add_argument(
        "--jd",
        default=None,
        help="Path to job description text file or - for stdin. Defaults to scratch current_jd.txt.",
    )
    parser.add_argument(
        "--questions",
        default=None,
        help="Path to JSON file containing extracted screening questions.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all tracked leads.",
    )
    parser.set_defaults(handler=handle_track)


def register_leads(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "leads",
        help="List all tracked job opportunities in the leads vault.",
    )
    parser.set_defaults(handler=handle_leads)


def _render_leads_table(leads: list[dict[str, object]]) -> None:
    if not leads:
        print("No leads tracked yet. Run 'worksisyphus track --company <Name> ...' to add one.")
        return

    col_date = 10
    col_comp = 20
    col_role = 26
    col_status = 10
    col_q = 6

    header = (
        f"{'Date':<{col_date}}  "
        f"{'Company':<{col_comp}}  "
        f"{'Role':<{col_role}}  "
        f"{'Status':<{col_status}}  "
        f"{'Q#':<{col_q}}  "
        f"Folder"
    )
    divider = "-" * len(header)
    print(header)
    print(divider)

    for item in leads:
        d = str(item.get("date", ""))
        c = fit_column(str(item.get("company", "")), col_comp)
        r = fit_column(str(item.get("role", "")), col_role)
        s = fit_column(str(item.get("status", "")), col_status)
        q = str(item.get("question_count", 0))
        folder = str(item.get("folder", ""))
        print(f"{d:<{col_date}}  {c}  {r}  {s}  {q:<{col_q}}  {folder}")


def handle_leads(args: argparse.Namespace, read_input: InputReader) -> int:
    leads = list_leads()
    _render_leads_table(leads)
    return 0


def handle_track(args: argparse.Namespace, read_input: InputReader) -> int:
    if args.list:
        return handle_leads(args, read_input)

    if not args.company:
        print("error: --company is required to track a lead.", file=sys.stderr)
        return 1

    bridge = ScratchBridge()
    jd_text = ""

    if args.jd:
        jd_text = read_input.read(args.jd, "jd")
    else:
        # Check scratch
        scratch_file = bridge.scratch_dir / "current_jd.txt"
        if scratch_file.is_file():
            jd_text = scratch_file.read_text(encoding="utf-8")
        else:
            print(
                "error: No JD provided and no scratch file found. Pass --jd <file|-> or run 'worksisyphus ingest <url>'.",
                file=sys.stderr,
            )
            return 1

    questions_data = None
    if args.questions:
        q_path = Path(args.questions)
        if not q_path.is_file():
            raise FileNotFoundError(f"Questions file not found: {q_path}")
        questions_data = json.loads(q_path.read_text(encoding="utf-8"))

    folder = track_lead(
        company=args.company,
        role=args.role,
        jd_text=jd_text,
        url=args.url,
        questions=questions_data,
    )
    print(f"Tracked lead in vault: {folder}")
    return 0
