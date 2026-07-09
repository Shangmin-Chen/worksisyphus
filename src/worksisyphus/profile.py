"""Load the master experiences database. All string values are trusted TeX."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PROFILE_PATH = Path("templates/experiences.json")


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
    organization: str
    location: str
    role: str
    date: str
    bullets: tuple[str, ...] = ()


@dataclass(frozen=True)
class Project:
    name: str
    technologies: str
    date: str
    bullets: tuple[str, ...] = ()


@dataclass(frozen=True)
class Profile:
    contact: Contact
    education: tuple[Education, ...] = ()
    experiences: tuple[Experience, ...] = ()
    projects: tuple[Project, ...] = ()
    skills: dict[str, tuple[str, ...]] = field(default_factory=dict)


def load_profile(path: Path = DEFAULT_PROFILE_PATH) -> Profile:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Profile(
        contact=Contact(**data.get("contact", {"name": ""})),
        education=tuple(Education(**e) if "coursework" not in e else Education(**{**e, "coursework": tuple(e["coursework"])}) for e in data.get("education", [])),
        experiences=tuple(Experience(**{**e, "bullets": tuple(e.get("bullets", []))}) for e in data.get("experiences", [])),
        projects=tuple(Project(**{**p, "bullets": tuple(p.get("bullets", []))}) for p in data.get("projects", [])),
        skills={group: tuple(items) for group, items in data.get("skills", {}).items()},
    )


def planner_index(profile: Profile) -> str:
    """Compact database index Gemini selects from. IDs: E<n> experiences, P<n> projects, 1-based bullets."""
    lines: list[str] = ["EXPERIENCES:"]
    for i, exp in enumerate(profile.experiences, 1):
        lines.append(f"E{i}: {exp.role} at {exp.organization} ({exp.date})")
        for j, bullet in enumerate(exp.bullets, 1):
            lines.append(f"  E{i}.{j}: {bullet}")
    lines.append("PROJECTS:")
    for i, proj in enumerate(profile.projects, 1):
        lines.append(f"P{i}: {proj.name} [{proj.technologies}] ({proj.date})")
        for j, bullet in enumerate(proj.bullets, 1):
            lines.append(f"  P{i}.{j}: {bullet}")
    lines.append("SKILLS:")
    for group, items in profile.skills.items():
        lines.append(f"{group}: {', '.join(items)}")
    return "\n".join(lines)
