"""Lead tracker: saving, listing, and managing tracked job opportunities (Venue 1)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from ..domain.ingestion import ScreeningQuestion
from .application import slugify

DEFAULT_LEADS_DIR = Path("leads")


def _allocate_lead_target(leads_dir: Path, base_folder: Path) -> Path:
    """Find the next free folder name, appending _2, _3 on same-day collisions."""
    if not base_folder.exists():
        return base_folder
    ordinal = 2
    while True:
        candidate = leads_dir / f"{base_folder.name}_{ordinal}"
        if not candidate.exists():
            return candidate
        ordinal += 1


def track_lead(
    company: str,
    jd_text: str,
    role: str = "Software Engineer",
    url: str = "",
    questions: list[dict[str, Any]] | tuple[ScreeningQuestion, ...] | None = None,
    leads_dir: Path | None = None,
    when: date | None = None,
) -> Path:
    """Persist a job opportunity into the leads vault (leads/<stem>/) without compiling a resume."""
    if not company.strip():
        raise ValueError("Company name is required to track a lead.")
    if not jd_text.strip():
        raise ValueError("Job description text cannot be empty.")

    target_leads_dir = leads_dir if leads_dir is not None else DEFAULT_LEADS_DIR
    target_leads_dir.mkdir(parents=True, exist_ok=True)

    when = when or date.today()
    comp_slug = slugify(company)
    role_slug = slugify(role) if role.strip() else "swe"
    base_folder_name = f"{when.isoformat()}_{comp_slug}_{role_slug}"
    base_target = target_leads_dir / base_folder_name

    target_folder = _allocate_lead_target(target_leads_dir, base_target)
    target_folder.mkdir(parents=True, exist_ok=True)

    meta = {
        "company": company,
        "role": role or "Software Engineer",
        "url": url,
        "date": when.isoformat(),
        "status": "tracked",
    }

    (target_folder / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (target_folder / "jd.txt").write_text(jd_text, encoding="utf-8")

    if questions:
        q_data: list[dict[str, Any]] = []
        for q in questions:
            if isinstance(q, ScreeningQuestion):
                q_data.append(
                    {
                        "id": q.question_id,
                        "prompt": q.prompt,
                        "type": q.question_type,
                        "required": q.required,
                        "options": list(q.options),
                    }
                )
            elif isinstance(q, dict):
                q_data.append(q)
        (target_folder / "questions.json").write_text(json.dumps(q_data, indent=2) + "\n", encoding="utf-8")

    return target_folder


def list_leads(leads_dir: Path | None = None) -> list[dict[str, Any]]:
    """List all tracked leads from the leads directory."""
    target_leads_dir = leads_dir if leads_dir is not None else DEFAULT_LEADS_DIR
    if not target_leads_dir.is_dir():
        return []

    leads: list[dict[str, Any]] = []
    for d in sorted(target_leads_dir.iterdir(), reverse=True):
        if not d.is_dir() or d.name.startswith("."):
            continue
        meta_file = d / "meta.json"
        if not meta_file.is_file():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        q_file = d / "questions.json"
        q_count = 0
        if q_file.is_file():
            try:
                q_list = json.loads(q_file.read_text(encoding="utf-8"))
                if isinstance(q_list, list):
                    q_count = len(q_list)
            except Exception:
                pass

        leads.append(
            {
                "folder": d.name,
                "path": d,
                "company": meta.get("company", "Unknown"),
                "role": meta.get("role", "Software Engineer"),
                "url": meta.get("url", ""),
                "date": meta.get("date", ""),
                "status": meta.get("status", "tracked"),
                "question_count": q_count,
            }
        )
    return leads


def resolve_lead_folder(stem_or_name: str, leads_dir: Path | None = None) -> Path:
    """Find a lead folder by exact name or substring match."""
    target_leads_dir = leads_dir if leads_dir is not None else DEFAULT_LEADS_DIR
    if not target_leads_dir.is_dir():
        raise FileNotFoundError(f"Leads directory not found: {target_leads_dir}")

    exact = target_leads_dir / stem_or_name
    if exact.is_dir():
        return exact

    # Search by partial stem
    matches = [
        d for d in target_leads_dir.iterdir() if d.is_dir() and stem_or_name in d.name and not d.name.startswith(".")
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        match_names = [m.name for m in matches]
        raise ValueError(f"Ambiguous lead stem '{stem_or_name}'. Matches: {match_names}")

    raise FileNotFoundError(f"Lead not found for stem '{stem_or_name}' in {target_leads_dir}")


def get_lead(stem_or_name: str, leads_dir: Path | None = None) -> tuple[Path, dict[str, Any], str]:
    """Retrieve folder path, metadata, and verbatim JD text for a tracked lead."""
    folder = resolve_lead_folder(stem_or_name, leads_dir)
    meta_file = folder / "meta.json"
    jd_file = folder / "jd.txt"

    if not meta_file.is_file():
        raise FileNotFoundError(f"Missing meta.json in {folder}")
    if not jd_file.is_file():
        raise FileNotFoundError(f"Missing jd.txt in {folder}")

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    jd_text = jd_file.read_text(encoding="utf-8")
    return folder, meta, jd_text


def update_lead_status(
    stem_or_name: str,
    status: str,
    leads_dir: Path | None = None,
) -> Path:
    """Update status of a tracked lead (e.g. 'applied', 'archived')."""
    folder = resolve_lead_folder(stem_or_name, leads_dir)
    meta_file = folder / "meta.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    meta["status"] = status
    meta_file.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return folder
