"""FileSystem Profile Loader: Reads JSON profile and parses into domain Profile."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ....core.domain.models import (
    DEFAULT_PROFILE_PATH,
    Contact,
    Education,
    Experience,
    Profile,
    Project,
)


def _require_dict(entry: Any, what: str, path: Path) -> bool:
    if not isinstance(entry, dict):
        raise ValueError(f"Invalid {what} in {path}: expected object, got {type(entry).__name__}")
    return True


def _require_section(data: dict[str, Any], section: str, expected: type, path: Path) -> Any:
    if section not in data:
        return expected()
    value = data[section]
    if not isinstance(value, expected):
        raise ValueError(
            f"Invalid {section} section in {path}: expected {expected.__name__}, got {type(value).__name__}"
        )
    return value


def _build(factory: Any, kwargs: dict[str, Any], what: str, path: Path) -> Any:
    """Build a dataclass, naming the offending entry and file on a schema mismatch."""
    try:
        return factory(**kwargs)
    except TypeError as exc:
        raise ValueError(f"Invalid {what} in {path}: {exc}") from exc


def load_profile(source: Path | str = DEFAULT_PROFILE_PATH) -> Profile:
    """Load profile directly from a profile.json file."""
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(
            f"Profile not found: {path}. If missing, recover from database with "
            f"`uv run worksisyphus db export-profile`."
        )

    text = path.read_text(encoding="utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    data = json.loads(text)
    education_entries = _require_section(data, "education", list, path)
    experiences_data = _require_section(data, "experiences", dict, path)
    projects_data = _require_section(data, "projects", dict, path)
    skills_data = _require_section(data, "skills", dict, path)
    skills: dict[str, tuple[str, ...]] = {}
    for group, items in skills_data.items():
        if not isinstance(items, list):
            raise ValueError(f"Invalid skills.{group} in {path}: expected list, got {type(items).__name__}")
        skills[group] = tuple(items)
    education: list[Education] = []
    for i, e in enumerate(education_entries):
        if not _require_dict(e, f"education entry {i}", path):
            continue
        label = f"education entry {i} ({e.get('institution', '?')})"
        coursework = e.get("coursework", [])
        if not isinstance(coursework, list):
            raise ValueError(f"Invalid coursework in {label} in {path}: expected list, got {type(coursework).__name__}")
        education.append(_build(Education, {**e, "coursework": tuple(coursework)}, label, path))
    if "contact" not in data:

        raise ValueError(f"Missing required 'contact' section in {path}")
    if not isinstance(data["contact"], dict):
        raise ValueError(f"Invalid contact section in {path}: expected object, got {type(data['contact']).__name__}")
    return Profile(
        contact=_build(Contact, data["contact"], "contact", path),
        education=tuple(education),

        experiences={
            slug: _build(Experience, {**e, "id": slug}, f"experience '{slug}'", path)
            for slug, e in experiences_data.items()
            if _require_dict(e, f"experience '{slug}'", path)
        },
        projects={
            slug: _build(Project, {**p, "id": slug}, f"project '{slug}'", path)
            for slug, p in projects_data.items()
            if _require_dict(p, f"project '{slug}'", path)
        },
        skills=skills,
    )


def profile_to_dict(profile: Profile) -> dict[str, Any]:
    """Serialize a Profile back into dictionary shape matching profile.json."""
    return {
        "contact": {
            "name": profile.contact.name,
            "email": profile.contact.email,
            "phone": profile.contact.phone,
            "website": profile.contact.website,
            "github": profile.contact.github,
            "linkedin": profile.contact.linkedin,
        },
        "education": [
            {
                "institution": edu.institution,
                "location": edu.location,
                "degree": edu.degree,
                "date": edu.date,
                "coursework": list(edu.coursework),
            }
            for edu in profile.education
        ],
        "experiences": {
            slug: {
                "role": exp.role,
                "org": exp.org,
                "location": exp.location,
                "date": exp.date,
                "bullets": dict(exp.bullets),
            }
            for slug, exp in profile.experiences.items()
        },
        "projects": {
            slug: {
                "name": proj.name,
                "tech": proj.tech,
                "date": proj.date,
                "bullets": dict(proj.bullets),
            }
            for slug, proj in profile.projects.items()
        },
        "skills": {cat: list(items) for cat, items in profile.skills.items()},
    }
