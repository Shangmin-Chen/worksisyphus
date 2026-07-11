"""Archive one application: frozen JD, plan, PDF, and status metadata.

Archived folders are immutable history — re-applying to the same company gets
a new dated folder; only meta.json's "status" is ever updated afterwards.
"""
from __future__ import annotations

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
    when = when or date.today()
    folder = applications_dir / f"{when.isoformat()}_{plan_path.stem}"
    if folder.exists():
        raise FileExistsError(f"{folder} already exists; archives are immutable, use a new plan name.")
    folder.mkdir(parents=True)
    shutil.copy2(plan_path, folder / "plan.json")
    shutil.copy2(pdf_path, folder / "resume.pdf")
    (folder / "jd.txt").write_text((jd_text.strip() or "No job description recorded.") + "\n", encoding="utf-8")
    meta = {"company": company, "role": role, "date": when.isoformat(), "source_url": source_url, "status": STATUSES[0]}
    (folder / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return folder
