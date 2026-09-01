"""Application lifecycle: 1-step apply, atomic compilation, tracking, and cloud sync."""

from __future__ import annotations

import errno
import json
import os
import re
import shutil
import tempfile
from collections.abc import Callable, Collection, Iterable
from dataclasses import replace as dataclass_replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .ats import ATSCheckResult, check_pdf_ats
from .compiler import CompileResult
from .gates import run_resume_gates
from .pipeline import tailor
from .profile import DEFAULT_PROFILE_PATH, Profile, load_profile

APPLICATIONS_DIR = Path("applications")
STATUSES = ("applied", "phone_screen", "onsite", "offer", "rejected")
STAGING_PREFIX = ".staging-"
TEX_BUILD_PREFIX = "worksisyphus-tex-"

Log = Callable[[str], None]

_APP_FOLDER_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<body>.+)$")
_ORDINAL_TAIL_RE = re.compile(r"^(?P<base>.+)_(?P<n>\d+)$")


def _silent(_: str) -> None:
    pass


def slugify(text: str) -> str:
    """Convert text into a clean filesystem/plan slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_-]+", "-", text).strip("-")


def parse_app_folder(name: str, siblings: Collection[str] = ()) -> tuple[str, str, int | None]:
    """Split an application folder name into (date, stem, ordinal).

    A trailing ``_N`` tail counts as the retry ordinal written by apply() only when N >= 2 and
    the unsuffixed base folder exists among siblings; anything else keeps the whole body as a
    literal stem, so legacy names that happen to end in digits stay intact.
    """
    match = _APP_FOLDER_RE.match(name)
    if not match:
        raise ValueError(f"Application folder {name!r} lacks a <YYYY-MM-DD>_ prefix.")
    date_str, body = match["date"], match["body"]
    tail = _ORDINAL_TAIL_RE.match(body)
    if tail and int(tail["n"]) >= 2 and f"{date_str}_{tail['base']}" in siblings:
        return date_str, tail["base"], int(tail["n"])
    return date_str, body, None


def application_sort_key(name: str, siblings: Collection[str] = ()) -> tuple[int, int, str, int]:
    """Listing order: newest date first, then retry order within a day reads top-to-bottom."""
    try:
        date_str, stem, ordinal = parse_app_folder(name, siblings)
        day = -date.fromisoformat(date_str).toordinal()
    except ValueError:
        # Unparsable names sink below every dated entry instead of crashing listings.
        return (1, 0, name, 0)
    return (0, day, stem, ordinal or 0)


def sorted_application_names(names: Collection[str]) -> list[str]:
    """Order application folder names newest-first; retry ordinals compare numerically."""
    return sorted(names, key=lambda name: application_sort_key(name, siblings=names))


def match_application_identifier(identifier: str, names: Iterable[str]) -> list[str]:
    """Resolve an identifier against candidate names: exact match first, else unique stem match."""
    all_names = list(names)
    exact = [name for name in all_names if name == identifier]
    if exact:
        return exact
    return [name for name in all_names if name.endswith(f"_{identifier}")]


def _allocate_target(applications_dir: Path, base_target: Path) -> Path:
    """Lowest free slot for a publish: the plain name first, then _2, _3, ..."""
    taken = {entry.name for entry in applications_dir.iterdir()}
    target = base_target
    ordinal = 1
    while target.name in taken:
        ordinal += 1
        target = base_target.parent / f"{base_target.name}_{ordinal}"
    return target


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

    # Deterministic naming strictly derived from company and role (#34). The underscore is the
    # folder grammar's structural separator (it delimits the retry ordinal), so slugify must
    # never emit one; this fails loudly instead of corrupting the namespace if that ever changes.
    comp_slug = slugify(company)
    role_slug = slugify(role) if role.strip() else "swe"
    if "_" in comp_slug or "_" in role_slug:
        raise ValueError(f"Slug for {company!r}/{role!r} contains '_': {comp_slug}_{role_slug}")
    app_stem = f"{comp_slug}_{role_slug}"

    base_target = applications_dir / f"{when.isoformat()}_{app_stem}"

    active_profile = profile if profile is not None else load_profile(profile_path)
    normalized_plan = plan_text.replace("\r\n", "\n").replace("\r", "\n")

    # Atomic publication: stage inside applications_dir so the final publish is a same-filesystem
    # os.replace rather than a file-by-file copy that can fail halfway and leave a partial folder.
    # LaTeX intermediates get their own temp dir so concurrent applies never clobber tex_files/.
    applications_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=applications_dir))
    tex_build_dir = Path(tempfile.mkdtemp(prefix=TEX_BUILD_PREFIX))
    try:
        # 1. Compile directly into the isolated staging dir
        compile_result = tailor(
            plan_text,
            profile=active_profile,
            profile_path=profile_path,
            plan_name=app_stem,
            pdf_dir=staging_dir,
            tex_dir=tex_build_dir,
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
            raise RuntimeError(f"Quality gate check failed for {base_target.name}:\n{reasons}")

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

        # 4. Atomic publish with retry allocation. Compilation is slow enough that a concurrent
        #    apply could claim the plain slot first; os.replace onto a non-empty directory fails
        #    with ENOTEMPTY, so the loser re-allocates the next free suffix and retries with the
        #    staged content it already paid for. Published folders are never mutated or consumed.
        while True:
            target_folder = _allocate_target(applications_dir, base_target)
            # mkdtemp is 0700; widen to match a normally-created directory.
            os.chmod(staging_dir, 0o755)
            try:
                os.replace(staging_dir, target_folder)
                break
            except OSError as exc:
                if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST):
                    raise
    except BaseException:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(tex_build_dir, ignore_errors=True)

    compile_result = dataclass_replace(compile_result, pdf_path=target_folder / "Simon_Chen_Resume.pdf")

    # 5. Database persistence (fatal on failure) and cloud sync (reported, non-fatal)
    from .db import DEFAULT_DB_PATH, get_connection, save_application_to_db

    if applications_dir == APPLICATIONS_DIR and DEFAULT_DB_PATH.is_file():
        conn = get_connection(DEFAULT_DB_PATH)
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
    """
    applications_dir = applications_dir if applications_dir is not None else APPLICATIONS_DIR
    scored: list[tuple[str, float | None]] = []
    if not applications_dir.is_dir():
        return scored
    candidate_name = (profile if profile is not None else load_profile(profile_path)).contact.name

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
            candidate_name=candidate_name,
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
    """List all applications with metadata, newest date first (retry order within a day)."""
    applications_dir = applications_dir if applications_dir is not None else APPLICATIONS_DIR
    apps: list[dict[str, str]] = []
    if not applications_dir.is_dir():
        return apps
    entries = [entry for entry in applications_dir.iterdir() if entry.is_dir() and not entry.name.startswith(".")]
    names = sorted_application_names([entry.name for entry in entries])
    by_name = {entry.name: entry for entry in entries}
    for name in names:
        folder = by_name[name]
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

    names = [
        folder.name
        for folder in sorted(applications_dir.iterdir())
        if folder.is_dir() and not folder.name.startswith(".")
    ]
    matches = match_application_identifier(app_identifier, names)
    if not matches:
        raise FileNotFoundError(f"No application folder found matching {app_identifier!r} in {applications_dir}.")
    if len(matches) > 1:
        listed = "\n".join(f"  {name}" for name in matches)
        raise ValueError(
            f"Application identifier {app_identifier!r} is ambiguous ({len(matches)} matches):\n{listed}\n"
            "Re-run with one of the full folder names above."
        )
    return applications_dir / matches[0]


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
