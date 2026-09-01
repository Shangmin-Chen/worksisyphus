"""Load the slug-keyed master profile database. All string values are trusted TeX."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_PROFILE_PATH = Path("profile.json")
REQUIRED_CONTACT_FIELDS = ("name", "email", "phone")


@dataclass(frozen=True)
class Contact:
    name: str
    email: str = ""
    phone: str = ""
    website: str = ""
    github: str = ""
    linkedin: str = ""


@dataclass(frozen=True)
class Education:
    institution: str
    location: str
    degree: str
    date: str
    coursework: tuple[str, ...] = ()


@dataclass(frozen=True)
class Experience:
    id: str
    role: str
    org: str
    location: str
    date: str
    bullets: dict[str, str] = field(default_factory=dict)  # slug -> TeX line, file order


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    tech: str
    date: str
    bullets: dict[str, str] = field(default_factory=dict)  # slug -> TeX line, file order


@dataclass(frozen=True)
class Profile:
    contact: Contact
    education: tuple[Education, ...] = ()
    experiences: dict[str, Experience] = field(default_factory=dict)
    projects: dict[str, Project] = field(default_factory=dict)
    skills: dict[str, tuple[str, ...]] = field(default_factory=dict)


def validate_contact(contact: Contact, source: str = "profile.json") -> None:
    """Ensure required contact details (name, email, phone) are present and non-empty."""
    for field_name in REQUIRED_CONTACT_FIELDS:
        if not getattr(contact, field_name, "").strip():
            raise ValueError(
                f"contact.{field_name} is empty in {source}; a resume cannot be rendered without contact info."
            )


def load_profile(source: Path | str = DEFAULT_PROFILE_PATH) -> Profile:
    """Load profile directly from a profile.json file."""
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(
            f"Profile not found: {path}. If missing, recover from database with "
            f"`uv run worksisyphus db export-profile`."
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    return Profile(
        contact=Contact(**data.get("contact", {"name": ""})),
        education=tuple(
            Education(**{**e, "coursework": tuple(e.get("coursework", []))}) for e in data.get("education", [])
        ),
        experiences={slug: Experience(id=slug, **e) for slug, e in data.get("experiences", {}).items()},
        projects={slug: Project(id=slug, **p) for slug, p in data.get("projects", {}).items()},
        skills={group: tuple(items) for group, items in data.get("skills", {}).items()},
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
        "skills": {group: list(items) for group, items in profile.skills.items()},
    }


def profile_index(profile: Profile) -> str:
    """Human-readable slug index: everything a plan file can reference."""
    lines: list[str] = ["EXPERIENCES:"]
    for slug, exp in profile.experiences.items():
        lines.append(f"{slug}: {exp.role} at {exp.org} ({exp.date})")
        for bullet_slug, bullet in exp.bullets.items():
            lines.append(f"  {slug}.{bullet_slug}: {bullet}")
    lines.append("PROJECTS:")
    for slug, proj in profile.projects.items():
        lines.append(f"{slug}: {proj.name} [{proj.tech}] ({proj.date})")
        for bullet_slug, bullet in proj.bullets.items():
            lines.append(f"  {slug}.{bullet_slug}: {bullet}")
    lines.append("SKILLS:")
    for group, items in profile.skills.items():
        lines.append(f"{group}: {', '.join(items)}")
    return "\n".join(lines)
