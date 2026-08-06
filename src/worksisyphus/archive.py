"""Archive one application: frozen JD, plan, PDF, and status metadata.

Archived folders are immutable history — re-applying to the same company gets
a new dated folder; only meta.json's "status" is ever updated afterwards.
"""
from __future__ import annotations

import hashlib
import json
import shutil
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
    if prov_path.is_file():
        try:
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
            expected_hash = hashlib.sha256(plan_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
            if prov.get("plan_hash") != expected_hash:
                raise ValueError(
                    f"The compiled PDF at {pdf_path} was compiled from a different plan (provenance mismatch). "
                    f"Run `worksisyphus tailor --plan {plan_path}` before archiving."
                )
        except (json.JSONDecodeError, OSError):
            pass

    when = when or date.today()
    folder = applications_dir / f"{when.isoformat()}_{plan_path.stem}"
    if folder.exists():
        raise FileExistsError(f"{folder} already exists; archives are immutable, use a new plan name.")
    folder.mkdir(parents=True)
    shutil.copy2(plan_path, folder / "plan.json")
    shutil.copy2(pdf_path, folder / "Simon_Chen_Resume.pdf")
    (folder / "jd.txt").write_text(jd_text.strip() + "\n", encoding="utf-8")
    meta = {"company": company, "role": role, "date": when.isoformat(), "source_url": source_url, "status": STATUSES[0]}
    (folder / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
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
        if meta_file.is_file():
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                data["folder"] = folder.name
                apps.append(data)
            except json.JSONDecodeError:
                pass
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

    target_folder: Path | None = None
    for folder in sorted(applications_dir.iterdir()):
        if not folder.is_dir():
            continue
        if folder.name == app_identifier or folder.name.endswith(f"_{app_identifier}") or app_identifier in folder.name:
            target_folder = folder
            break

    if target_folder is None:
        raise FileNotFoundError(f"No application folder found matching {app_identifier!r} in {applications_dir}.")

    meta_file = target_folder / "meta.json"
    if not meta_file.is_file():
        raise FileNotFoundError(f"Missing meta.json in {target_folder}.")

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    old_status = meta.get("status", "unknown")
    meta["status"] = new_status
    meta_file.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return target_folder, old_status, new_status

