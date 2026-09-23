"""Apply subcommand handler: 1-step tailor, validate, freeze into applications/, and ATS verify."""

from __future__ import annotations

import argparse
import json

from .....core.use_cases import optimizer as optimizer_module
from .. import commands
from ..helpers import InputReader, add_compiler_config_flags, build_compiler_config


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "apply",
        help="Tailor, validate, compile directly into applications/<app>, and run ATS checks.",
    )
    parser.add_argument(
        "--company",
        required=True,
        help="Company name (e.g. Google, Jane Street). Normalized into the folder name.",
    )
    parser.add_argument(
        "--jd",
        required=True,
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
    jd_text = read_input.read(args.jd, "jd")
    if args.plan:
        plan_text = read_input.read(args.plan, "plan")
    else:
        best_plan, _, _ = optimizer_module.optimize_plan(profile, jd_text, role_name=args.role or "software_engineer")
        plan_text = json.dumps(best_plan, indent=2)

    config = build_compiler_config(args)
    folder, _compile_res, ats_res = commands.apply_app(
        plan_text=plan_text,
        jd_text=jd_text,
        company=args.company,
        role=args.role,
        source_url=args.url,
        config=config,
        log=print,
    )
    print(f"Exported {folder / 'Simon_Chen_Resume.pdf'} (1 page).")
    print(f"ATS check: {'passed' if ats_res.passed else 'failed'} ({ats_res.word_count} words extracted)")
    for warning in ats_res.warnings:
        print(f"WARN: {warning}")
    print(f"Application created: {folder}")
    return 0
