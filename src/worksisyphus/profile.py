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


def _total_bullets(profile: Profile) -> int:
    return sum(len(exp.bullets) for exp in profile.experiences.values()) + sum(
        len(proj.bullets) for proj in profile.projects.values()
    )


def _append_field_difference(
    differences: list[str],
    prefix: str,
    field_name: str,
    profile_value: object,
    db_value: object,
) -> None:
    if profile_value != db_value:
        differences.append(f"{prefix} {field_name}: profile has {profile_value!r}, database has {db_value!r}")


def profile_content_differences(profile: Profile, db_profile: Profile) -> list[str]:
    """Compare non-contact profile content and return actionable difference strings."""
    differences: list[str] = []

    if len(profile.education) != len(db_profile.education):
        differences.append(
            f"profile has {len(profile.education)} education record(s), database has {len(db_profile.education)}"
        )
    else:
        for index, (profile_edu, db_edu) in enumerate(
            zip(profile.education, db_profile.education, strict=True), start=1
        ):
            prefix = f"education record {index}"
            _append_field_difference(differences, prefix, "institution", profile_edu.institution, db_edu.institution)
            _append_field_difference(differences, prefix, "location", profile_edu.location, db_edu.location)
            _append_field_difference(differences, prefix, "degree", profile_edu.degree, db_edu.degree)
            _append_field_difference(differences, prefix, "date", profile_edu.date, db_edu.date)
            _append_field_difference(differences, prefix, "coursework", profile_edu.coursework, db_edu.coursework)

    profile_experience_slugs = set(profile.experiences)
    db_experience_slugs = set(db_profile.experiences)
    if len(profile.experiences) != len(db_profile.experiences) or profile_experience_slugs != db_experience_slugs:
        parts = [f"profile has {len(profile.experiences)} experiences, database has {len(db_profile.experiences)}"]
        missing_from_profile = sorted(db_experience_slugs - profile_experience_slugs)
        missing_from_db = sorted(profile_experience_slugs - db_experience_slugs)
        if missing_from_profile:
            parts.append(f"{', '.join(repr(slug) for slug in missing_from_profile)} missing from profile")
        if missing_from_db:
            parts.append(f"{', '.join(repr(slug) for slug in missing_from_db)} missing from database")
        differences.append(": ".join(parts))

    for slug in sorted(profile_experience_slugs & db_experience_slugs):
        profile_exp = profile.experiences[slug]
        db_exp = db_profile.experiences[slug]
        prefix = f"experience {slug!r}"
        _append_field_difference(differences, prefix, "role", profile_exp.role, db_exp.role)
        _append_field_difference(differences, prefix, "org", profile_exp.org, db_exp.org)
        _append_field_difference(differences, prefix, "location", profile_exp.location, db_exp.location)
        _append_field_difference(differences, prefix, "date", profile_exp.date, db_exp.date)
        profile_bullet_slugs = set(profile_exp.bullets)
        db_bullet_slugs = set(db_exp.bullets)
        if len(profile_exp.bullets) != len(db_exp.bullets) or profile_bullet_slugs != db_bullet_slugs:
            message = (
                f"experience {slug!r} has {len(profile_exp.bullets)} bullets in profile, "
                f"{len(db_exp.bullets)} in database"
            )
            missing_from_profile = sorted(db_bullet_slugs - profile_bullet_slugs)
            if missing_from_profile:
                message += (
                    f": {', '.join(repr(bullet_slug) for bullet_slug in missing_from_profile)} missing from profile"
                )
            differences.append(message)
        for bullet_slug in sorted(profile_bullet_slugs & db_bullet_slugs):
            if profile_exp.bullets[bullet_slug] != db_exp.bullets[bullet_slug]:
                differences.append(f"experience {slug!r}.{bullet_slug!r} text differs between profile and database")

    profile_project_slugs = set(profile.projects)
    db_project_slugs = set(db_profile.projects)
    if len(profile.projects) != len(db_profile.projects) or profile_project_slugs != db_project_slugs:
        parts = [f"profile has {len(profile.projects)} projects, database has {len(db_profile.projects)}"]
        missing_from_profile = sorted(db_project_slugs - profile_project_slugs)
        missing_from_db = sorted(profile_project_slugs - db_project_slugs)
        if missing_from_profile:
            parts.append(f"{', '.join(repr(slug) for slug in missing_from_profile)} missing from profile")
        if missing_from_db:
            parts.append(f"{', '.join(repr(slug) for slug in missing_from_db)} missing from database")
        differences.append(": ".join(parts))

    for slug in sorted(profile_project_slugs & db_project_slugs):
        profile_proj = profile.projects[slug]
        db_proj = db_profile.projects[slug]
        prefix = f"project {slug!r}"
        _append_field_difference(differences, prefix, "name", profile_proj.name, db_proj.name)
        _append_field_difference(differences, prefix, "tech", profile_proj.tech, db_proj.tech)
        _append_field_difference(differences, prefix, "date", profile_proj.date, db_proj.date)
        profile_bullet_slugs = set(profile_proj.bullets)
        db_bullet_slugs = set(db_proj.bullets)
        if len(profile_proj.bullets) != len(db_proj.bullets) or profile_bullet_slugs != db_bullet_slugs:
            message = (
                f"project {slug!r} has {len(profile_proj.bullets)} bullets in profile, "
                f"{len(db_proj.bullets)} in database"
            )
            missing_from_profile = sorted(db_bullet_slugs - profile_bullet_slugs)
            if missing_from_profile:
                message += (
                    f": {', '.join(repr(bullet_slug) for bullet_slug in missing_from_profile)} missing from profile"
                )
            differences.append(message)
        for bullet_slug in sorted(profile_bullet_slugs & db_bullet_slugs):
            if profile_proj.bullets[bullet_slug] != db_proj.bullets[bullet_slug]:
                differences.append(f"project {slug!r}.{bullet_slug!r} text differs between profile and database")

    profile_skill_groups = set(profile.skills)
    db_skill_groups = set(db_profile.skills)
    if profile_skill_groups != db_skill_groups:
        parts = [f"profile has {len(profile.skills)} skill group(s), database has {len(db_profile.skills)}"]
        missing_from_profile = sorted(db_skill_groups - profile_skill_groups)
        missing_from_db = sorted(profile_skill_groups - db_skill_groups)
        if missing_from_profile:
            parts.append(f"{', '.join(repr(group) for group in missing_from_profile)} missing from profile")
        if missing_from_db:
            parts.append(f"{', '.join(repr(group) for group in missing_from_db)} missing from database")
        differences.append(": ".join(parts))
    else:
        for group in sorted(profile_skill_groups):
            if profile.skills[group] != db_profile.skills[group]:
                differences.append(f"skill group {group!r} differs between profile and database")

    return differences


def profile_drift_summary(profile: Profile, db_profile: Profile) -> str | None:
    """Return a short human-readable drift summary, or None when content matches."""
    differences = profile_content_differences(profile, db_profile)
    if not differences:
        return None

    profile_bullets = _total_bullets(profile)
    db_bullets = _total_bullets(db_profile)
    if profile_bullets < db_bullets:
        delta = db_bullets - profile_bullets
        return f"profile.json is {delta} bullet{'s' if delta != 1 else ''} behind the database"

    if len(profile.experiences) < len(db_profile.experiences):
        delta = len(db_profile.experiences) - len(profile.experiences)
        return f"profile.json is {delta} experience{'s' if delta != 1 else ''} behind the database"

    if len(profile.projects) < len(db_profile.projects):
        delta = len(db_profile.projects) - len(profile.projects)
        return f"profile.json is {delta} project{'s' if delta != 1 else ''} behind the database"

    return differences[0]


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
