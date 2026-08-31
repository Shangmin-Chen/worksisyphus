"""Application lifecycle: 1-step apply, atomic compilation, tracking, and cloud sync."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import replace as dataclass_replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .ats import ATSCheckResult, check_pdf_ats
from .compiler import CompileResult
from .gates import run_resume_gates
from .pipeline import tailor
from .profile import DEFAULT_PROFILE_PATH, Contact, Profile, load_profile, validate_contact

APPLICATIONS_DIR = Path("applications")
STATUSES = ("applied", "phone_screen", "onsite", "offer", "rejected")
STAGING_PREFIX = ".staging-"

Log = Callable[[str], None]


def _silent(_: str) -> None:
    pass


def slugify(text: str) -> str:
    """Convert text into a clean filesystem/plan slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_-]+", "-", text).strip("-")


def _resolve_db_path(db_path: Path | None, applications_dir: Path) -> Path | None:
    """Which database this run should cross-check and record against, or None for neither.

    An explicit db_path always wins. Otherwise the default database is used only for a real
    delivery into applications/; a run staged into some other directory (tests, scratch
    builds) must not touch the live store. Imported lazily: db.py is a store, not a source,
    and the render path must not depend on it at import time.
    """
    if db_path is not None:
        return Path(db_path)
    from .db import DEFAULT_DB_PATH

    return DEFAULT_DB_PATH if applications_dir == APPLICATIONS_DIR else None


def cross_check_contact_against_db(
    contact: Contact,
    db_path: Path | None,
    log: Log = _silent,
) -> bool:
    """Compare the profile's contact block against the independent copy in the database.

    This is the check that would have caught the incident. profile.json vanished and a
    fixture with a scrubbed contact block stood in for it; every quality gate passed,
    because each one compares the rendered PDF against the very profile that rendered it.
    The database still held the real name, email and phone the whole time -- so a second,
    independent copy is the only thing that can contradict a wrong profile.

    Returns True when the cross-check actually ran. A missing database or a database with no
    contact row is skipped and logged, never treated as agreement: the rules in
    validate_contact still apply, so a fresh clone or CI is protected but not silently
    "verified".
    """
    if db_path is None:
        log("Contact cross-check skipped: this run is not writing to the default database.")
        return False
    if not db_path.is_file():
        log(f"Contact cross-check skipped: no database at {db_path} (fresh clone or CI). Rule checks still applied.")
        return False

    from .db import get_connection, load_profile_from_db

    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contact'")
        if cur.fetchone() is None:
            log(f"Contact cross-check skipped: {db_path} has no contact table. Run `uv run worksisyphus db sync`.")
            return False
        db_contact = load_profile_from_db(conn).contact
    finally:
        conn.close()

    if not any((db_contact.name, db_contact.email, db_contact.phone)):
        log(f"Contact cross-check skipped: {db_path} has no contact row. Run `uv run worksisyphus db sync`.")
        return False

    mismatches = [
        f"contact.{field_name}: profile has {getattr(contact, field_name)!r}, database has {getattr(db_contact, field_name)!r}"
        for field_name in ("name", "email", "phone", "website", "github", "linkedin")
        if getattr(contact, field_name) != getattr(db_contact, field_name)
    ]
    if mismatches:
        joined = "\n".join(f"- {m}" for m in mismatches)
        raise ValueError(
            f"Contact details disagree with {db_path}; refusing to build a resume until they match.\n{joined}\n"
            f"The database is the surviving copy: if profile.json is the one that is wrong, restore it with "
            f"`uv run worksisyphus db export-profile --force`. If profile.json is right, publish it with "
            f"`uv run worksisyphus db sync`."
        )
    return True


def apply(
    plan_text: str,
    jd_text: str,
    company: str,
    role: str = "",
    source_url: str = "",
    when: date | None = None,
    profile: Profile | None = None,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    applications_dir: Path | None = None,
    db_path: Path | None = None,
    sync_cloud: bool = True,
    log: Log = _silent,
) -> tuple[Path, CompileResult, ATSCheckResult]:
    """Tailor, validate, compile atomically into applications/<app>, run ATS/quality gates, and sync."""
    if not jd_text.strip():
        raise ValueError("jd_text is empty; pass the job description or a note explaining its absence.")
    if not company.strip():
        raise ValueError("company name is required.")
    if not plan_text.strip():
        raise ValueError("Plan is empty.")

    applications_dir = applications_dir if applications_dir is not None else APPLICATIONS_DIR
    when = when or date.today()

    # Contact validation runs before anything is compiled or staged. A resume with a dead
    # email is worse than no resume, and no downstream gate can catch one: they all compare
    # the PDF against the same profile that rendered it. Failing here costs a few
    # milliseconds and leaves no artifacts behind.
    active_profile = profile if profile is not None else load_profile(profile_path)
    validate_contact(active_profile.contact, source=str(profile_path))
    resolved_db_path = _resolve_db_path(db_path, applications_dir)
    cross_check_contact_against_db(active_profile.contact, resolved_db_path, log=log)

    # Deterministic naming strictly derived from company and role (#34)
    comp_slug = slugify(company)
    role_slug = slugify(role) if role.strip() else "swe"
    app_stem = f"{comp_slug}_{role_slug}"

    target_folder = applications_dir / f"{when.isoformat()}_{app_stem}"
    if target_folder.exists():
        raise FileExistsError(f"{target_folder} already exists; applications are immutable, use a new date or role.")

    normalized_plan = plan_text.replace("\r\n", "\n").replace("\r", "\n")

    # Atomic publication: stage inside applications_dir so the final publish is a same-filesystem
    # os.replace rather than a file-by-file copy that can fail halfway and leave a partial folder.
    applications_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=applications_dir))
    try:
        # 1. Compile directly into the isolated staging dir
        compile_result = tailor(
            plan_text,
            profile=active_profile,
            profile_path=profile_path,
            plan_name=app_stem,
            pdf_dir=staging_dir,
            log=log,
        )

        # 2. Freeze the plan and JD. meta.json is written after scoring, below, so the folder
        #    is never published without the evaluation that belongs to it.
        (staging_dir / "plan.json").write_text(normalized_plan.strip() + "\n", encoding="utf-8")
        (staging_dir / "jd.txt").write_text(jd_text.strip() + "\n", encoding="utf-8")
        meta: dict[str, Any] = {
            "company": company,
            "role": role,
            "date": when.isoformat(),
            "source_url": source_url,
            "status": STATUSES[0],
        }
        # 3. Quality gates and ATS validation, reusing a single PDF extraction
        gate_results, ats_result = run_resume_gates(
            staging_dir / "Simon_Chen_Resume.pdf",
            candidate_name=active_profile.contact.name,
            candidate_email=active_profile.contact.email,
            candidate_phone=active_profile.contact.phone,
            expected_pages=1,
        )
        failed_gates = [g for g in gate_results if not g.passed]
        if failed_gates:
            reasons = "\n".join(f"- {g.gate_name}: {'; '.join(g.diagnostics)}" for g in failed_gates)
            raise RuntimeError(f"Quality gate check failed for {target_folder.name}:\n{reasons}")

        # 3b. Score the delivered resume against this JD and record it alongside the application,
        #     so every application carries the evaluation that was true when it was sent.
        evaluation = evaluate_application(
            resume_text=ats_result.text,
            jd_text=jd_text,
            role=role,
            candidate_name=active_profile.contact.name,
        )
        meta["evaluation"] = evaluation
        (staging_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

        # 4. Atomic publish. Re-check the target: compilation is slow enough that a concurrent
        #    apply could have claimed the slot since the check above, and os.replace would
        #    silently consume an empty directory.
        if target_folder.exists():
            raise FileExistsError(
                f"{target_folder} already exists; applications are immutable, use a new date or role."
            )
        # mkdtemp is 0700; widen to match a normally-created directory.
        os.chmod(staging_dir, 0o755)
        os.replace(staging_dir, target_folder)
    except BaseException:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    compile_result = dataclass_replace(compile_result, pdf_path=target_folder / "Simon_Chen_Resume.pdf")

    # 5. Database persistence (fatal on failure) and cloud sync (reported, non-fatal)
    from .db import get_connection, save_application_to_db

    if resolved_db_path is not None and resolved_db_path.is_file():
        conn = get_connection(resolved_db_path)
        try:
            save_application_to_db(
                conn=conn,
                app_id=target_folder.name,
                company=company,
                role=role,
                date_str=when.isoformat(),
                source_url=source_url,
                status=STATUSES[0],
                # Store the same canonical (stripped) form seed_database derives from the files on
                # disk, so a reseed does not see a phantom change on every application row.
                jd_text=jd_text.strip(),
                plan_json=normalized_plan.strip(),
                evaluation_json=json.dumps(evaluation, sort_keys=True),
            )
        finally:
            conn.close()

        if sync_cloud:
            _sync_cloud(log)

    return target_folder, compile_result, ats_result


def evaluate_application(
    resume_text: str,
    jd_text: str,
    role: str,
    candidate_name: str = "",
) -> dict[str, Any]:
    """Score a resume with the HackerRank hiring agent, keyed to the role it was sent for.

    The role title is free text ("Founding Product Engineer"); load_role normalizes it, uses a
    curated rubric when one exists, and otherwise synthesizes one in memory from the JD.
    """
    from .hiring_agent import HackerRankHiringAgent

    agent = HackerRankHiringAgent(role_name=role or "software_engineer", jd_text=jd_text)
    result = agent.evaluate(resume_text=resume_text, candidate_name=candidate_name)
    return {
        "role_rubric": agent.role.name,
        "role_title": agent.role.position_title,
        "total_score": result.get("total_score"),
        "max_possible": result.get("max_possible"),
        "scores": result.get("scores", {}),
        "bonus_points": result.get("bonus_points", {}),
        "deductions": result.get("deductions", {}),
        "key_strengths": result.get("key_strengths", []),
        "areas_for_improvement": result.get("areas_for_improvement", []),
        "evaluated_at": datetime.now(UTC).isoformat(),
    }


def _lazy_candidate_name(profile: Profile | None, profile_path: Path, log: Log) -> Callable[[], str]:
    """Resolve the candidate name on first use, tolerating an absent profile.

    Used only by the scoring path, which labels a report and delivers nothing. A missing
    profile there is a degraded label, not a dead resume, so it is logged and the scoring
    continues; the delivery path (apply) still refuses outright.
    """
    resolved: list[str] = []

    def resolve() -> str:
        if not resolved:
            if profile is not None:
                resolved.append(profile.contact.name)
            else:
                try:
                    resolved.append(load_profile(profile_path).contact.name)
                except FileNotFoundError:
                    log(f"No {profile_path} on disk; scoring without a candidate name (nothing is delivered here).")
                    resolved.append("")
        return resolved[0]

    return resolve


def backfill_evaluations(
    applications_dir: Path | None = None,
    overwrite: bool = False,
    profile: Profile | None = None,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    log: Log = _silent,
) -> list[tuple[str, float | None]]:
    """Score applications that predate evaluation recording, writing into meta.json.

    Returns (application_id, total_score) for each one scored. Existing evaluations are kept
    unless overwrite is set, so re-running is safe and idempotent.

    Backfill re-scores resumes that were already delivered; it publishes nothing, so it must
    not require the live profile.json. The candidate name is resolved lazily and only if some
    application actually needs scoring -- an eager load made a run over an explicitly named
    applications_dir fail on any checkout without a profile (it is gitignored), which since
    load_profile stopped falling back to the fixture means every fresh clone and CI.
    """
    applications_dir = applications_dir if applications_dir is not None else APPLICATIONS_DIR
    scored: list[tuple[str, float | None]] = []
    if not applications_dir.is_dir():
        return scored
    resolve_name = _lazy_candidate_name(profile, profile_path, log)

    for folder in sorted(applications_dir.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        meta_file = folder / "meta.json"
        pdf = folder / "Simon_Chen_Resume.pdf"
        jd_file = folder / "jd.txt"
        if not meta_file.is_file() or not pdf.is_file():
            log(f"Skipped {folder.name}: missing meta.json or resume")
            continue

        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if meta.get("evaluation") and not overwrite:
            continue

        resume_text = check_pdf_ats(pdf).text
        jd_text = jd_file.read_text(encoding="utf-8") if jd_file.is_file() else ""
        evaluation = evaluate_application(
            resume_text=resume_text,
            jd_text=jd_text,
            role=meta.get("role", ""),
            candidate_name=resolve_name(),
        )
        meta["evaluation"] = evaluation
        temporary = meta_file.with_name(f"{meta_file.name}.tmp")
        temporary.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        temporary.replace(meta_file)
        scored.append((folder.name, evaluation.get("total_score")))
        log(f"Scored {folder.name}: {evaluation.get('total_score')}/{evaluation.get('max_possible')}")
    return scored


def _sync_cloud(log: Log) -> bool:
    """Push local database state to Turso, reporting failure rather than swallowing it.

    sync_to_turso signals failure by returning False rather than raising, so the return
    value must be checked; the try/except only guards against unexpected import or call errors.
    """
    from .db import sync_to_turso

    try:
        synced = sync_to_turso()
    except Exception as exc:
        log(f"Warning: Turso cloud sync failed: {exc}")
        return False
    if not synced:
        log("Warning: Turso cloud sync did not complete (CLI missing, auth expired, or push rejected).")
    return synced


def list_applications(applications_dir: Path | None = None) -> list[dict[str, str]]:
    """List all applications with metadata, sorted by date descending."""
    applications_dir = applications_dir if applications_dir is not None else APPLICATIONS_DIR
    apps: list[dict[str, str]] = []
    if not applications_dir.is_dir():
        return apps
    for folder in sorted(applications_dir.iterdir(), reverse=True):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        meta_file = folder / "meta.json"
        if not meta_file.is_file():
            raise ValueError(f"Missing meta.json in {folder}; the application folder is incomplete.")
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"Invalid meta.json in {folder}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Invalid meta.json in {folder}: expected a JSON object.")
        data["folder"] = folder.name
        apps.append(data)
    return apps


def resolve_application_folder(
    app_identifier: str,
    applications_dir: Path | None = None,
) -> Path:
    """Find a unique matching application folder by full folder name or plan stem."""
    if not app_identifier.strip():
        raise ValueError("Application identifier must not be empty.")

    applications_dir = applications_dir if applications_dir is not None else APPLICATIONS_DIR
    if not applications_dir.is_dir():
        raise FileNotFoundError(f"No application folder found matching {app_identifier!r} in {applications_dir}.")

    folders = [
        folder for folder in sorted(applications_dir.iterdir()) if folder.is_dir() and not folder.name.startswith(".")
    ]
    exact_matches = [folder for folder in folders if folder.name == app_identifier]
    stem_matches = [folder for folder in folders if folder.name.endswith(f"_{app_identifier}")]
    matches = exact_matches or stem_matches
    if not matches:
        raise FileNotFoundError(f"No application folder found matching {app_identifier!r} in {applications_dir}.")
    if len(matches) > 1:
        names = ", ".join(folder.name for folder in matches)
        raise ValueError(f"Application identifier {app_identifier!r} is ambiguous; use one of: {names}")
    return matches[0]


def update_application_status(
    app_identifier: str,
    new_status: str,
    applications_dir: Path | None = None,
    sync_cloud: bool = True,
    log: Log = _silent,
) -> tuple[Path, str, str]:
    """Atomically update status in an application's meta.json.

    Returns (folder_path, old_status, new_status).
    """
    if new_status not in STATUSES:
        raise ValueError(f"Invalid status {new_status!r}. Must be one of: {', '.join(STATUSES)}")

    applications_dir = applications_dir if applications_dir is not None else APPLICATIONS_DIR
    target_folder = resolve_application_folder(app_identifier, applications_dir=applications_dir)

    meta_file = target_folder / "meta.json"
    if not meta_file.is_file():
        raise FileNotFoundError(f"Missing meta.json in {target_folder}.")

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise ValueError(f"Invalid meta.json in {target_folder}: expected a JSON object.")
    old_status = meta.get("status", "unknown")
    meta["status"] = new_status
    temporary_meta = meta_file.with_name(f"{meta_file.name}.tmp")
    temporary_meta.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    temporary_meta.replace(meta_file)

    from .db import DEFAULT_DB_PATH, get_connection, update_application_status_in_db

    if applications_dir == APPLICATIONS_DIR and DEFAULT_DB_PATH.is_file():
        conn = get_connection(DEFAULT_DB_PATH)
        try:
            update_application_status_in_db(conn, target_folder.name, new_status)
        finally:
            conn.close()

        if sync_cloud:
            _sync_cloud(log)

    return target_folder, old_status, new_status
