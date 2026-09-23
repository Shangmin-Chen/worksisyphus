"""Evaluate subcommand handler: deterministic ATS & rubric evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from .....core.domain.plan import parse_plan
from .....core.domain.rules import full_selection
from .....core.use_cases.application import resolve_application_folder
from .....core.use_cases.evaluator import (
    evaluate_pdf_against_jd,
    evaluate_resume_text,
    format_evaluation_report,
    selection_to_plain_text,
)
from .. import commands
from ..helpers import InputReader


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("evaluate", help="Score a resume PDF or plan against a target job description.")
    parser.add_argument("--plan", default=None, help="Plan JSON file or - for stdin.")
    parser.add_argument(
        "--resume",
        default=None,
        help="Resume PDF path to evaluate (defaults to the most recent application's resume).",
    )
    parser.add_argument("--jd", default=None, help="Job description text file or - for stdin.")
    parser.add_argument("--app", default=None, help="Application folder name or unique stem to evaluate.")
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Evaluate the full profile.json canonical database directly without a PDF or plan.",
    )
    parser.add_argument(
        "--role",
        default="software_engineer",
        help="Target role name for evaluation reporting.",
    )
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace, read_input: InputReader) -> int:
    profile = commands.load_profile()
    resume_text = ""
    pdf_path: Path | None = None
    role_label = "Target Role"

    if args.app:
        app_path = resolve_application_folder(args.app)
        jd_file = app_path / "jd.txt"
        if not jd_file.is_file():
            raise FileNotFoundError(f"Missing jd.txt in {app_path}")
        jd_text = jd_file.read_text(encoding="utf-8")
        pdf_path = app_path / "Simon_Chen_Resume.pdf"
        role_label = app_path.name
    else:
        if not args.jd:
            raise ValueError("Job description required: pass --jd <file|-> or --app <name>")
        jd_text = read_input.read(args.jd, "jd")

        if args.profile:
            selection = full_selection(profile)
            resume_text = selection_to_plain_text(selection, profile)
            role_label = "profile_json"
        elif args.resume:
            pdf_path = Path(args.resume)
            role_label = pdf_path.stem
        elif args.plan:
            plan_text = read_input.read(args.plan, "plan")
            selection = parse_plan(plan_text, profile)
            resume_text = selection_to_plain_text(selection, profile)
            role_label = Path(args.plan).stem
        else:
            pdf_path = commands._latest_application_pdf()
            if pdf_path is not None and pdf_path.is_file():
                role_label = pdf_path.parent.name
            else:
                resume_text = selection_to_plain_text(full_selection(profile), profile)
                role_label = "profile_json"

    if pdf_path and pdf_path.is_file():
        report = evaluate_pdf_against_jd(pdf_path, jd_text, candidate_name=profile.contact.name)
    else:
        report = evaluate_resume_text(
            resume_text,
            jd_text,
            candidate_name=profile.contact.name,
            pdf_path=pdf_path,
        )
    print(format_evaluation_report(report, target_role=role_label))
    return 0
