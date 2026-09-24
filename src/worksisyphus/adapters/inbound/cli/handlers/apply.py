"""Apply subcommand handler: 1-step tailor, validate, freeze into applications/, and ATS verify."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .....core.use_cases import optimizer as optimizer_module
from .....core.use_cases.tracker import get_lead, update_lead_status
from ....outbound.ingestion.http_fetcher import HttpRawFetcher
from ....outbound.ingestion.pre_cleaner import clean_html
from ....outbound.ingestion.scratch_bridge import ScratchBridge
from .. import commands
from ..helpers import InputReader, add_compiler_config_flags, build_compiler_config


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "apply",
        help="Tailor, validate, compile directly into applications/<app>, and run ATS checks.",
    )
    parser.add_argument(
        "--company",
        default="",
        help="Company name (e.g. Google, Jane Street). Normalized into the folder name.",
    )
    parser.add_argument(
        "--jd",
        default=None,
        help="Path to job description text file, or - for stdin. Refuses empty text.",
    )
    parser.add_argument(
        "--role",
        default="",
        help="Target role (e.g. Systems Engineer). Stored in meta.json and reflected in the folder name.",
    )
    parser.add_argument(
        "--url",
        default="",
        help="URL of the job posting. Stored in meta.json for traceability.",
    )
    parser.add_argument(
        "--lead",
        default=None,
        help="Tracked lead stem to apply to from the leads vault (e.g. 2026-09-23_stripe_swe).",
    )
    parser.add_argument(
        "--plan",
        default=None,
        help="Path to a plan JSON file, or - for stdin. If omitted, uses the knapsack optimizer.",
    )
    # Legacy flags accepted as no-ops for backward compatibility
    parser.add_argument("--no-sync", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--allow-branch", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-git-check", action="store_true", help=argparse.SUPPRESS)

    add_compiler_config_flags(parser)
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace, read_input: InputReader) -> int:
    profile = commands.load_profile()
    company = args.company
    role = args.role
    source_url = args.url
    jd_text = ""
    lead_folder: Path | None = None

    if args.lead:
        lead_folder, lead_meta, lead_jd = get_lead(args.lead)
        company = company or lead_meta.get("company", "")
        role = role or lead_meta.get("role", "")
        source_url = source_url or lead_meta.get("url", "")
        jd_text = lead_jd
    elif args.jd:
        jd_text = read_input.read(args.jd, "jd")
    elif args.url:
        fetcher = HttpRawFetcher()
        payload = fetcher.fetch(args.url)
        jd_text = clean_html(payload.raw_content)
        bridge = ScratchBridge()
        bridge.save_current_jd(jd_text)
    else:
        raise ValueError("Job description required: pass --jd <file|->, --url <url>, or --lead <stem>.")

    if not company:
        raise ValueError("Company name is required: pass --company <name> (or --lead <stem>).")

    if args.plan:
        plan_text = read_input.read(args.plan, "plan")
    else:
        best_plan, _, _ = optimizer_module.optimize_plan(profile, jd_text, role_name=role or "software_engineer")
        plan_text = json.dumps(best_plan, indent=2)

    config = build_compiler_config(args)
    folder, _compile_res, ats_res = commands.apply_app(
        plan_text=plan_text,
        jd_text=jd_text,
        company=company,
        role=role,
        source_url=source_url,
        config=config,
        log=print,
    )

    if lead_folder is not None:
        q_src = lead_folder / "questions.json"
        if q_src.is_file():
            shutil.copy2(q_src, folder / "questions.json")
        update_lead_status(args.lead, "applied")

    print(f"Exported {folder / 'Simon_Chen_Resume.pdf'} (1 page).")
    print(f"ATS check: {'passed' if ats_res.passed else 'failed'} ({ats_res.word_count} words extracted)")
    for warning in ats_res.warnings:
        print(f"WARN: {warning}")
    print(f"Application created: {folder}")
    return 0
