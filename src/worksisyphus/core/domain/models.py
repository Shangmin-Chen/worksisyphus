"""Domain entities, value objects, and domain invariants for worksisyphus."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_PROFILE_PATH = Path("profile.json")
REQUIRED_CONTACT_FIELDS = ("name", "email", "phone")
TAILORED_NAME = "Simon_Chen_Resume"


class PlanError(ValueError):
    """The plan references something the profile does not contain."""


@dataclass(frozen=True)
class Contact:
    """Candidate contact information and social/portfolio profiles."""

    name: str
    email: str = ""
    phone: str = ""
    website: str = ""
    github: str = ""
    linkedin: str = ""


@dataclass(frozen=True)
class Education:
    """Educational institution, degree, timeline, and coursework."""

    institution: str
    location: str
    degree: str
    date: str
    coursework: tuple[str, ...] = ()


@dataclass(frozen=True)
class Experience:
    """Work experience entry with bullet points mapped by slug."""

    id: str
    role: str
    org: str
    location: str
    date: str
    bullets: dict[str, str] = field(default_factory=dict)  # slug -> TeX line, file order


@dataclass(frozen=True)
class Project:
    """Technical project entry with technologies and bullet points."""

    id: str
    name: str
    tech: str
    date: str
    bullets: dict[str, str] = field(default_factory=dict)  # slug -> TeX line, file order


@dataclass(frozen=True)
class Profile:
    """Single source of truth master profile database."""

    contact: Contact
    education: tuple[Education, ...] = ()
    experiences: dict[str, Experience] = field(default_factory=dict)
    projects: dict[str, Project] = field(default_factory=dict)
    skills: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class Pick:
    """One selected experience/project: its slug plus the chosen bullet slugs."""

    id: str
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class Selection:
    """Ranked selection (most relevant first) plus the output file name."""

    name: str
    experiences: tuple[Pick, ...]
    projects: tuple[Pick, ...]
    skills: dict[str, tuple[str, ...]]


def validate_contact(contact: Contact, source: str = "profile.json") -> None:
    """Ensure required contact details (name, email, phone) are present and non-empty."""
    for field_name in REQUIRED_CONTACT_FIELDS:
        if not getattr(contact, field_name, "").strip():
            raise ValueError(
                f"contact.{field_name} is empty in {source}; a resume cannot be rendered without contact info."
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
