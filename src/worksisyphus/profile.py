"""Load the slug-keyed master profile database. All string values are trusted TeX."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PROFILE_PATH = Path("profile.json")


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


def load_profile(source: Path | str | Any = DEFAULT_PROFILE_PATH) -> Profile:
    """Load profile from SQLite DB if available/given, or from profile.json."""
    if hasattr(source, "execute"):
        from .db import load_profile_from_db
        return load_profile_from_db(source)

    path = Path(source)
    if path.suffix in (".db", ".sqlite", ".sqlite3") and path.is_file():
        from .db import get_connection, load_profile_from_db
        conn = get_connection(path)
        try:
            return load_profile_from_db(conn)
        finally:
            conn.close()

    from .db import DEFAULT_DB_PATH, get_connection, load_profile_from_db
    if path == DEFAULT_PROFILE_PATH and DEFAULT_DB_PATH.is_file():
        try:
            conn = get_connection(DEFAULT_DB_PATH)
            try:
                return load_profile_from_db(conn)
            finally:
                conn.close()
        except Exception:
            pass

    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        return Profile(
            contact=Contact(**data.get("contact", {"name": ""})),
            education=tuple(Education(**{**e, "coursework": tuple(e.get("coursework", []))}) for e in data.get("education", [])),
            experiences={slug: Experience(id=slug, **e) for slug, e in data.get("experiences", {}).items()},
            projects={slug: Project(id=slug, **p) for slug, p in data.get("projects", {}).items()},
            skills={group: tuple(items) for group, items in data.get("skills", {}).items()},
        )
    raise FileNotFoundError(f"Profile not found: {source}")


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
