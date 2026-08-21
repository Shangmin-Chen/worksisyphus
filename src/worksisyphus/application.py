"""Application lifecycle: 1-step apply, compiling, tracking, and cloud sync."""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from datetime import date
from pathlib import Path

from .ats import ATSCheckResult, check_pdf_ats
from .compiler import CompileResult
from .pipeline import PDF_DIR, tailor
from .profile import DEFAULT_PROFILE_PATH

APPLICATIONS_DIR = Path("applications")
STATUSES = ("applied", "phone_screen", "onsite", "offer", "rejected")

Log = Callable[[str], None]


def _silent(_: str) -> None:
    pass


def slugify(text: str) -> str:
    """Convert text into a clean filesystem/plan slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_-]+", "-", text).strip("-")


def apply(
    plan_text: str,
    jd_text: str,
    company: str,
    role: str = "",
    source_url: str = "",
    plan_name: str = "",
    when: date | None = None,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    applications_dir: Path | None = None,
    pdf_dir: Path = PDF_DIR,
    sync_cloud: bool = True,
    log: Log = _silent,
) -> tuple[Path, CompileResult, ATSCheckResult]:
    """Tailor, validate, compile directly into applications/<app>, run ATS check, and sync."""
    if not jd_text.strip():
        raise ValueError("jd_text is empty; pass the job description or a note explaining its absence.")
    if not company.strip():
        raise ValueError("company name is required.")
    if not plan_text.strip():
        raise ValueError("Plan is empty.")

    applications_dir = applications_dir if applications_dir is not None else APPLICATIONS_DIR
    when = when or date.today()
    if plan_name.strip():
        app_stem = slugify(plan_name)
    else:
        comp_slug = slugify(company)
        role_slug = slugify(role) if role.strip() else "swe"
        app_stem = f"{comp_slug}_{role_slug}"

    folder = applications_dir / f"{when.isoformat()}_{app_stem}"
    if folder.exists():
        raise FileExistsError(f"{folder} already exists; applications are immutable, use a new date or plan name.")
    folder.mkdir(parents=True)

    # 1. Compile directly into the application folder
    compile_result = tailor(
        plan_text,
        profile_path=profile_path,
        plan_name=app_stem,
        pdf_dir=folder,
        log=log,
    )

    # 2. Mirror latest PDF to resumes/Simon_Chen_Resume.pdf for convenience
    pdf_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(folder / "Simon_Chen_Resume.pdf", pdf_dir / "Simon_Chen_Resume.pdf")

    # 3. Write plan, JD, and metadata into application directory
    normalized_plan = plan_text.replace("\r\n", "\n").replace("\r", "\n")
    (folder / "plan.json").write_text(normalized_plan.strip() + "\n", encoding="utf-8")
    (folder / "jd.txt").write_text(jd_text.strip() + "\n", encoding="utf-8")
    meta = {
        "company": company,
        "role": role,
        "date": when.isoformat(),
        "source_url": source_url,
        "status": STATUSES[0],
    }
    (folder / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # 4. Quality gates validation (ATS, No-GPA, Banned Content, LaTeX Leaks, Density)
    from .gates import check_resume_gates
    from .profile import load_profile

    profile = load_profile(profile_path)
    gate_results = check_resume_gates(
        folder / "Simon_Chen_Resume.pdf",
        candidate_name=profile.contact.name,
        candidate_email=profile.contact.email,
        candidate_phone=profile.contact.phone,
        expected_pages=1,
    )
    failed_gates = [g for g in gate_results if not g.passed]
    if failed_gates:
        reasons = "\n".join(f"- {g.gate_name}: {'; '.join(g.diagnostics)}" for g in failed_gates)
        raise RuntimeError(f"Quality gate check failed for {folder.name}:\n{reasons}")

    ats_result = check_pdf_ats(folder / "Simon_Chen_Resume.pdf")

    # 5. Database insertion & Cloud Sync
    from .db import DEFAULT_DB_PATH, get_connection, save_application_to_db, sync_to_turso

    if applications_dir == APPLICATIONS_DIR and DEFAULT_DB_PATH.is_file():
        try:
            conn = get_connection(DEFAULT_DB_PATH)
            try:
                save_application_to_db(
                    conn=conn,
                    app_id=folder.name,
                    company=company,
                    role=role,
                    date_str=when.isoformat(),
                    source_url=source_url,
                    status=STATUSES[0],
                    jd_text=jd_text.strip(),
                    plan_json=normalized_plan,
                )
            finally:
                conn.close()

            if sync_cloud:
                sync_to_turso()
        except Exception:
            pass

    return folder, compile_result, ats_result


def list_applications(applications_dir: Path | None = None) -> list[dict[str, str]]:
    """List all applications with metadata, sorted by date descending."""
    applications_dir = applications_dir if applications_dir is not None else APPLICATIONS_DIR
    apps: list[dict[str, str]] = []
    if not applications_dir.is_dir():
        return apps
    for folder in sorted(applications_dir.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        meta_file = folder / "meta.json"
        if not meta_file.is_file():
            raise ValueError(f"Missing meta.json in {folder}.")
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

    folders = [folder for folder in sorted(applications_dir.iterdir()) if folder.is_dir()]
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

    from .db import DEFAULT_DB_PATH, get_connection, sync_to_turso, update_application_status_in_db

    if applications_dir == APPLICATIONS_DIR and DEFAULT_DB_PATH.is_file():
        try:
            conn = get_connection(DEFAULT_DB_PATH)
            try:
                update_application_status_in_db(conn, target_folder.name, new_status)
            finally:
                conn.close()

            if sync_cloud:
                sync_to_turso()
        except Exception:
            pass

    return target_folder, old_status, new_status
