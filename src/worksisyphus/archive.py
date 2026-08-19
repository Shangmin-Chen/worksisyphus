"""Archive one application: frozen JD, plan, PDF, and status metadata.

Archived folders are immutable history — re-applying to the same company gets
a new dated folder; only meta.json's "status" is ever updated afterwards.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

APPLICATIONS_DIR = Path("applications")
STATUSES = ("applied", "phone_screen", "onsite", "offer", "rejected")


def archive_application(
    plan_path: Path,
    pdf_path: Path,
    jd_text: str,
    company: str,
    role: str = "",
    source_url: str = "",
    when: date | None = None,
    applications_dir: Path = APPLICATIONS_DIR,
) -> Path:
    """Freeze an application into applications/<date>_<plan-stem>/ and return the folder."""
    if not pdf_path.is_file():
        raise FileNotFoundError(f"{pdf_path} does not exist; run tailor before archiving.")
    if not jd_text.strip():
        raise ValueError("jd_text is empty; pass the job description or a note explaining its absence.")

    prov_path = pdf_path.parent / ".provenance.json"
    if not prov_path.is_file():
        raise ValueError(
            f"No build provenance found for {pdf_path}. Run `worksisyphus tailor --plan {plan_path}` before archiving."
        )
    try:
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Could not validate build provenance at {prov_path}: {exc}") from exc
    if (
        not isinstance(prov, dict)
        or not isinstance(prov.get("plan_hash"), str)
        or not isinstance(prov.get("pdf_hash"), str)
    ):
        raise ValueError(f"Could not validate build provenance at {prov_path}: missing plan_hash or pdf_hash.")
    plan_bytes = plan_path.read_bytes()
    normalized_plan = plan_bytes.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    expected_plan_hash = hashlib.sha256(normalized_plan.encode("utf-8")).hexdigest()
    if prov["plan_hash"] != expected_plan_hash:
        raise ValueError(
            f"The compiled PDF at {pdf_path} was compiled from a different plan (provenance mismatch). "
            f"Run `worksisyphus tailor --plan {plan_path}` before archiving."
        )
    pdf_bytes = pdf_path.read_bytes()
    expected_pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    if prov["pdf_hash"] != expected_pdf_hash:
        raise ValueError(
            f"The compiled PDF at {pdf_path} changed after tailoring (provenance mismatch). "
            f"Run `worksisyphus tailor --plan {plan_path}` before archiving."
        )

    when = when or date.today()
    folder = applications_dir / f"{when.isoformat()}_{plan_path.stem}"
    if folder.exists():
        raise FileExistsError(f"{folder} already exists; archives are immutable, use a new plan name.")
    folder.mkdir(parents=True)
    (folder / "plan.json").write_bytes(plan_bytes)
    (folder / "Simon_Chen_Resume.pdf").write_bytes(pdf_bytes)
    (folder / "jd.txt").write_text(jd_text.strip() + "\n", encoding="utf-8")
    meta = {"company": company, "role": role, "date": when.isoformat(), "source_url": source_url, "status": STATUSES[0]}
    (folder / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    from .db import DEFAULT_DB_PATH, archive_application_to_db, get_connection

    if DEFAULT_DB_PATH.is_file():
        try:
            conn = get_connection(DEFAULT_DB_PATH)
            try:
                archive_application_to_db(
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
        except Exception:
            pass

    return folder


def list_applications(applications_dir: Path = APPLICATIONS_DIR) -> list[dict[str, str]]:
    """List all archived applications with metadata, sorted by date descending."""
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


def update_application_status(
    app_identifier: str,
    new_status: str,
    applications_dir: Path = APPLICATIONS_DIR,
) -> tuple[Path, str, str]:
    """Update status in meta.json for a matching application folder.

    Returns (folder_path, old_status, new_status).
    """
    if new_status not in STATUSES:
        raise ValueError(f"Invalid status {new_status!r}. Must be one of: {', '.join(STATUSES)}")
    if not app_identifier.strip():
        raise ValueError("Application identifier must not be empty.")

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
    target_folder = matches[0]

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

    if DEFAULT_DB_PATH.is_file():
        try:
            conn = get_connection(DEFAULT_DB_PATH)
            try:
                update_application_status_in_db(conn, target_folder.name, new_status)
            finally:
                conn.close()
        except Exception:
            pass

    return target_folder, old_status, new_status
