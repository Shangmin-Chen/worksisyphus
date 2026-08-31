"""Load the slug-keyed master profile database. All string values are trusted TeX."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_PROFILE_PATH = Path("profile.json")

#: Contact fields without which a resume cannot be answered. Everything else (website,
#: github, linkedin) is a nice-to-have a recruiter can do without.
REQUIRED_CONTACT_FIELDS = ("name", "email", "phone")

#: Literal placeholder fragments, all of them present in tests/fixtures/profile.json.
#: Matched case-insensitively against every contact field, required or not.
PLACEHOLDER_FRAGMENTS = (
    "example.com",
    "example.org",
    "@example.",
    "linkedin.com/in/example",
    "github.com/example",
    "your-name",
    "yourname",
    "555-555-5555",
)

#: The 555 exchange is reserved for fiction in the North American numbering plan, so any
#: number whose exchange is 555 (555-0100, 617-555-1234, +1 555 555 5555) is fake. This
#: pattern only sees *separated* forms: its leading \b needs a non-word character before the
#: 555, so a compact "3475550100" slipped past it. It is kept as the fallback for shapes the
#: positional check below cannot parse, because a review verified it has no false positives
#: on real formats.
PLACEHOLDER_PHONE_RE = re.compile(r"\b\(?555\)?[-.\s]?\d{4}\b")

_NON_DIGITS_RE = re.compile(r"\D")

#: How to get real contact details back. The database is the only other copy on disk.
_RECOVERY_HINT = (
    "profile.json is gitignored, so git will not report it wrong and git checkout will not "
    "restore it. Recover the real contact block from the database with "
    "`uv run worksisyphus db export-profile --force`."
)


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


def load_profile(source: Path | str = DEFAULT_PROFILE_PATH) -> Profile:
    """Load profile directly from a profile.json file.

    A missing profile is a hard error, never a fallback. profile.json is gitignored
    (cloud-backed), so its absence is invisible to `git status`, and every other profile
    on disk -- tests/fixtures/profile.json above all -- carries a scrubbed contact block.
    Substituting one renders a resume that passes every quality gate (one page, ATS,
    no-GPA, content density) while addressing the recruiter to simon@example.com.
    Silence here ships undeliverable resumes; fail loudly instead.
    """
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(
            f"Profile not found: {path}. profile.json is gitignored, so git will not report it "
            f"missing and git checkout will not restore it. Recover it from the database with "
            f"`uv run worksisyphus db export-profile`. "
            f"Do not substitute tests/fixtures/profile.json: its contact block is scrubbed to "
            f"example.com placeholders."
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


def _is_fictional_phone(value: str) -> bool:
    """True when the number's exchange is 555, the block the NANP reserves for fiction.

    Textual matching fails in both directions, so this matches by *position* instead.
    Requiring a separator before the 555 (``PLACEHOLDER_PHONE_RE``) let the compact forms
    ``3475550100`` and ``+13475550100`` -- both 347-555-0100 -- through, while searching the
    stripped digits for a bare "555" would reject real numbers that merely contain those
    digits somewhere else: ``212-955-5187`` becomes 2129555187 and ``+44 20 7555 0123``
    becomes 442075550123. The exchange is digits 4-6 of a 10-digit NANP number (or the first
    three of a bare 7-digit local number), and nowhere else.

    Anything that is not NANP-shaped -- a UK number, a number carrying an extension -- falls
    back to the regex. A false positive here blocks a legitimate resume build, which is worse
    than the false negative being fixed, so the fallback stays as narrow as it was.
    """
    digits = _NON_DIGITS_RE.sub("", value)
    if len(digits) == 11 and digits.startswith("1"):  # +1 / 1- country code
        digits = digits[1:]
    if len(digits) == 10:
        return digits[3:6] == "555"
    if len(digits) == 7:  # bare local number, e.g. 555-0100
        return digits.startswith("555")
    return bool(PLACEHOLDER_PHONE_RE.search(value))


def validate_contact(contact: Contact, source: str = "profile.json", recovery_hint: str = _RECOVERY_HINT) -> None:
    """Fail closed on contact details that cannot reach a human.

    Two rules, both structural:

    1. ``name``, ``email`` and ``phone`` must be non-empty. ``website``, ``github`` and
       ``linkedin`` stay optional -- a resume without a portfolio link is still deliverable.
    2. No field, required or optional, may hold a placeholder (example.com, a 555 exchange,
       github.com/example, ...).

    This exists because the quality gates cannot catch a bad header: they compare the
    rendered PDF against the same profile that rendered it, so a resume addressed to
    simon@example.com passes every one of them. Four were sent that way. Validate the
    profile against the rules, not against itself.

    ``recovery_hint`` overrides the closing sentence for callers validating something other
    than profile.json. The default hint points at the database, which is only sound advice
    while the database is the good copy: a caller checking the *database* must pass its own
    hint, or the error would tell the user to repair a bad profile from the very copy that
    just failed.
    """
    for field_name in REQUIRED_CONTACT_FIELDS:
        if not getattr(contact, field_name, "").strip():
            raise ValueError(
                f"contact.{field_name} is empty in {source}; a resume without it cannot be answered. {recovery_hint}"
            )

    for field_name in ("name", "email", "phone", "website", "github", "linkedin"):
        value = getattr(contact, field_name, "")
        if not value:
            continue
        lowered = value.lower()
        hit = next((fragment for fragment in PLACEHOLDER_FRAGMENTS if fragment in lowered), None)
        if hit is None and field_name == "phone" and _is_fictional_phone(value):
            hit = "the 555 exchange, reserved for fictional numbers"
        if hit is not None:
            raise ValueError(
                f"contact.{field_name} in {source} is a placeholder: {value!r} contains {hit!r}. "
                f"This is what tests/fixtures/profile.json looks like, not a deliverable resume. "
                f"{recovery_hint}"
            )


def profile_to_dict(profile: Profile) -> dict[str, Any]:
    """Serialize a Profile back into the exact nested shape of profile.json.

    The inverse of ``load_profile``'s parsing half, and the single place that shape is
    written down. Both the database seeder and ``db export-profile`` go through it, so
    neither has to re-implement "what profile.json looks like" -- re-implementing the
    *reading* half is precisely how the fixture fallback survived in seed_database after
    load_profile was hardened against it.
    """
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
