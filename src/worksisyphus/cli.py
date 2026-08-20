"""Tiny CLI for compiling, tailoring, archiving, and tracking applications."""

from __future__ import annotations

import argparse
import json
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
    return text if len(text) <= width else f"{text[: width - 1]}…"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worksisyphus", description="Resume compiler.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("compile", help="Rebuild the canonical full resume.")
    sub.add_parser("index", help="Print every slug a plan file can reference.")
    tailor_cmd = sub.add_parser("tailor", help="Compile a one-page resume from a plan file of slugs.")
    tailor_cmd.add_argument("--plan", required=True, help="Path to a plan JSON file, or - for stdin.")
    tailor_cmd.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite unarchived tailored resume without warning.",
    )
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
    db_cmd = sub.add_parser("db", help="Manage SQLite and Turso database layer.")
    db_sub = db_cmd.add_subparsers(dest="db_action", required=True)
    db_sub.add_parser("init", help="Initialize and seed database from profile.json and applications/.")
    db_sub.add_parser("sync", help="Sync database: export profile.json and push to Turso cloud.")
    db_sub.add_parser("status", help="Show database metrics and connection status.")
    history_cmd = db_sub.add_parser("history", help="Show append-only audit trail.")
    history_cmd.add_argument("--limit", type=int, default=20, help="Number of audit events to display.")
    history_cmd.add_argument("--type", dest="entity_type", default=None, help="Filter by entity type.")
    eval_cmd = sub.add_parser("evaluate", help="Score a resume PDF or plan against a target job description.")
    eval_cmd.add_argument("--plan", default=None, help="Plan JSON file to evaluate.")
    eval_cmd.add_argument(
        "--resume",
        default=None,
        help="Resume PDF path to evaluate (defaults to resumes/Simon_Chen_Resume.pdf).",
    )
    eval_cmd.add_argument("--jd", default=None, help="Job description text file or - for stdin.")
    eval_cmd.add_argument("--app", default=None, help="Archived application folder or unique stem to evaluate.")
    eval_cmd.add_argument(
        "--profile",
        action="store_true",
        help="Evaluate the full profile.json canonical database directly without a PDF or plan.",
    )
    eval_cmd.add_argument(
        "--hackerrank",
        action="store_true",
        help="Run 1:1 HackerRank hiring agent rubric evaluation.",
    )
    eval_cmd.add_argument(
        "--check-upstream",
        action="store_true",
        help="Check HackerRank upstream repository commit status and rubric sync.",
    )
    eval_cmd.add_argument(
        "--role",
        default="software_engineer",
        help="Role rubric for HackerRank evaluation (e.g. software_engineer, product_engineer, startup_product_engineer, ai_engineer, mle, systems_engineer, quant_engineer, software_engineering_intern).",
    )
    opt_cmd = sub.add_parser("optimize", help="Combinatorially search and find the highest-scoring plan for a JD.")
    opt_cmd.add_argument("--jd", required=True, help="Job description text file or - for stdin.")
    opt_cmd.add_argument(
        "--role",
        default="software_engineer",
        help="Role rubric to optimize against.",
    )
    opt_cmd.add_argument("--output", default=None, help="Optional plan JSON file path to write winning plan to.")
    args = parser.parse_args(argv)

    try:
        if args.command == "compile":
            build_canonical(log=print)
        elif args.command == "index":
            print(profile_index(load_profile()))
        elif args.command == "validate":
            print(_describe(parse_plan(_read_plan(args.plan), load_profile())))
        elif args.command == "archive":
            if args.plan == "-":
                raise ValueError("archive requires a plan file path, not stdin (use --plan <path>).")
            plan_path = Path(args.plan)
            if not plan_path.is_file():
                raise FileNotFoundError(f"Plan file not found: {plan_path}")
            selection = parse_plan(plan_path.read_text(encoding="utf-8"), load_profile())
            jd_text = _read_plan(args.jd)
            folder = archive_application(
                plan_path,
                PDF_DIR / f"{selection.name}.pdf",
                jd_text,
                company=args.company,
                role=args.role,
                source_url=args.url,
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
        elif args.command == "db":
            from .db import (
                DEFAULT_DB_PATH,
                export_profile_json,
                get_audit_history,
                get_connection,
                load_profile_from_db,
                seed_database,
                sync_to_turso,
            )

            conn = get_connection(DEFAULT_DB_PATH)
            try:
                if args.db_action == "init":
                    seed_database(conn)
                    print(f"Initialized and seeded {DEFAULT_DB_PATH}")
                    turso_ok = sync_to_turso()
                    print(f"Turso cloud sync: {'synced' if turso_ok else 'skipped / failed'}")
                elif args.db_action == "sync":
                    export_profile_json(conn)
                    print("Exported active database state to profile.json")
                    turso_ok = sync_to_turso()
                    print(f"Turso cloud sync: {'synced' if turso_ok else 'skipped / failed'}")
                elif args.db_action == "status":
                    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contact'")
                    if not cur.fetchone():
                        print("Database not initialized. Run 'worksisyphus db init' first.")
                        return 0
                    profile = load_profile_from_db(conn)
                    events = get_audit_history(conn, limit=1)
                    cur = conn.execute("SELECT count(*) FROM applications")
                    app_count = cur.fetchone()[0]
                    cur2 = conn.execute("SELECT count(*) FROM audit_events")
                    event_count = cur2.fetchone()[0]
                    print(f"Database: {DEFAULT_DB_PATH}")
                    print(f"Contact: {profile.contact.name} ({profile.contact.email})")
                    print(f"Education: {len(profile.education)} record(s)")
                    print(
                        f"Experiences: {len(profile.experiences)} with {sum(len(e.bullets) for e in profile.experiences.values())} bullets"
                    )
                    print(
                        f"Projects: {len(profile.projects)} with {sum(len(p.bullets) for p in profile.projects.values())} bullets"
                    )
                    print(
                        f"Skill Groups: {len(profile.skills)} ({sum(len(s) for s in profile.skills.values())} total skills)"
                    )
                    print(f"Tracked Applications: {app_count}")
                    print(f"Audit Events: {event_count}")
                elif args.db_action == "history":
                    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_events'")
                    if not cur.fetchone():
                        print("Database not initialized. Run 'worksisyphus db init' first.")
                        return 0
                    events = get_audit_history(conn, limit=args.limit, entity_type=args.entity_type)
                    if not events:
                        print("No audit events found.")
                    else:
                        header = f"{'Timestamp':<30} {'Action':<15} {'Entity':<20} {'ID':<35} Details"
                        print(header)
                        print("-" * len(header))
                        for ev in events:
                            details = ""
                            if ev["field_name"]:
                                details = f"{ev['field_name']}: {ev['old_value']} -> {ev['new_value']}"
                            elif ev["metadata"]:
                                details = json.dumps(ev["metadata"])
                            print(
                                f"{_fit_column(ev['timestamp'], 30):<30} "
                                f"{_fit_column(ev['action'], 15):<15} "
                                f"{_fit_column(ev['entity_type'], 20):<20} "
                                f"{_fit_column(ev['entity_id'], 35):<35} "
                                f"{details}"
                            )
            finally:
                conn.close()
        elif args.command == "evaluate":
            from .archive import resolve_application_folder
            from .ats import check_pdf_ats
            from .evaluator import (
                evaluate_pdf_against_jd,
                evaluate_resume_text,
                format_evaluation_report,
                selection_to_plain_text,
            )
            from .hiring_agent import (
                HackerRankHiringAgent,
                check_upstream_status,
                format_hackerrank_report,
            )

            if getattr(args, "check_upstream", False):
                status = check_upstream_status()
                print("=" * 68)
                print(f"HACKERRANK UPSTREAM SYNC STATUS: {status.get('upstream_repo', '')}")
                print("=" * 68)
                print(f"Status:          {status.get('status', '').upper()}")
                print(f"Local Commit:    {status.get('local_commit')}")
                print(f"Remote Commit:   {status.get('remote_commit')}")
                print(f"Synced Date:     {status.get('synced_date')}")
                print(f"Reference Role:  {status.get('reference_role')}")
                print(f"Custom Tracks:   {', '.join(status.get('custom_tracks', []))}")
                print(f"Message:         {status.get('message')}")
                print("=" * 68)
                return 0

            profile = load_profile()
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
                role_label = args.app
                if pdf_path.is_file():
                    resume_text = check_pdf_ats(pdf_path, name=profile.contact.name).text
            else:
                if not args.jd and not args.hackerrank:
                    raise ValueError("Job description required: pass --jd <file|->, --app <name>, or --hackerrank")
                jd_text = _read_plan(args.jd) if args.jd else ""

                if args.profile:
                    from .selection import full_selection

                    selection = full_selection(profile)
                    resume_text = selection_to_plain_text(selection, profile)
                    role_label = "profile_json"
                elif args.resume:
                    pdf_path = Path(args.resume)
                    role_label = pdf_path.stem
                    if pdf_path.is_file():
                        resume_text = check_pdf_ats(pdf_path, name=profile.contact.name).text
                elif args.plan:
                    plan_text = _read_plan(args.plan)
                    selection = parse_plan(plan_text, profile)
                    resume_text = selection_to_plain_text(selection, profile)
                    role_label = Path(args.plan).stem
                else:
                    pdf_path = PDF_DIR / "Simon_Chen_Resume.pdf"
                    role_label = "Simon_Chen_Resume"
                    if pdf_path.is_file():
                        resume_text = check_pdf_ats(pdf_path, name=profile.contact.name).text

            if args.hackerrank:
                agent = HackerRankHiringAgent(role_name=args.role, jd_text=jd_text)
                result = agent.evaluate(resume_text=resume_text, candidate_name=profile.contact.name)
                print(format_hackerrank_report(result, role_name=args.role))
            else:
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
        elif args.command == "optimize":
            from .optimizer import format_optimization_report, optimize_plan

            profile = load_profile()
            jd_text = _read_plan(args.jd)
            best_plan, best_eval, results = optimize_plan(profile, jd_text, role_name=args.role)
            print(format_optimization_report(best_plan, best_eval, results))
            if args.output:
                out_path = Path(args.output)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json.dumps(best_plan, indent=2) + "\n", encoding="utf-8")
                print(f"\nOptimal plan written to: {out_path}")
        else:
            plan_name = Path(args.plan).stem if args.plan != "-" else "stdin"
            tailor(
                _read_plan(args.plan),
                plan_name=plan_name,
                force=args.force,
                log=print,
            )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
