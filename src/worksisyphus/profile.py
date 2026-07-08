from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .models import (
    Bullet,
    CanonicalProfile,
    Contact,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
    SkillGroup,
    SkillItem,
    ValidationErrorDetail,
)

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


class ProfileValidationError(ValueError):
    def __init__(self, errors: Iterable[ValidationErrorDetail]) -> None:
        self.errors = tuple(errors)
        message = "; ".join(error.message for error in self.errors)
        super().__init__(message)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def slugify(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = _NON_ALNUM_RE.sub("-", ascii_text.lower()).strip("-")
    return slug or "item"


def normalize_id(value: Any) -> str:
    return _as_text(value).strip().lower()


def derive_legacy_id(namespace: str, *parts: Any) -> str:
    return f"{namespace}:{slugify(' '.join(_as_text(part) for part in parts if _as_text(part).strip()))}"


class _IdRegistry:
    def __init__(self) -> None:
        self._seen: dict[str, str] = {}
        self.errors: list[ValidationErrorDetail] = []

    def add(self, identifier: str, path: str, label: str) -> None:
        if not identifier:
            self.errors.append(
                ValidationErrorDetail(
                    code="invalid_id",
                    message=f"Canonical ID at {path} must not be empty.",
                    path=path,
                )
            )
            return
        existing = self._seen.get(identifier)
        if existing is not None:
            self.errors.append(
                ValidationErrorDetail(
                    code="duplicate_id",
                    message=f"Duplicate canonical ID {identifier!r} at {path}; first seen at {existing}.",
                    path=path,
                    identifier=identifier,
                )
            )
            return
        self._seen[identifier] = label


def load_canonical_profile(path: str | Path) -> CanonicalProfile:
    profile_path = Path(path)
    with profile_path.open("r", encoding="utf-8") as profile_file:
        raw = json.load(profile_file)
    return parse_canonical_profile(raw)


def parse_canonical_profile(raw: Mapping[str, Any]) -> CanonicalProfile:
    registry = _IdRegistry()
    contact = _parse_contact(raw.get("contact", {}))
    education = _parse_education(raw.get("education", []), registry)
    experiences = _parse_experiences(raw.get("experiences", []), registry)
    projects = _parse_projects(raw.get("projects", []), registry)
    skill_groups = _parse_skills(raw.get("skills", {}), registry)

    if registry.errors:
        raise ProfileValidationError(registry.errors)

    return CanonicalProfile(
        contact=contact,
        education=education,
        experiences=experiences,
        projects=projects,
        skill_groups=skill_groups,
    )


def _parse_contact(raw: Any) -> Contact:
    if not isinstance(raw, Mapping):
        raw = {}
    return Contact(
        name=_as_text(raw.get("name")),
        email=_as_text(raw.get("email")),
        phone=_as_text(raw.get("phone")),
        website=_as_text(raw.get("website")),
        github=_as_text(raw.get("github")),
        linkedin=_as_text(raw.get("linkedin")),
    )


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return []


def _entry_id(raw: Mapping[str, Any], derived_id: str) -> str:
    explicit_id = raw.get("id")
    return normalize_id(explicit_id) if explicit_id is not None else derived_id


def _parse_education(raw_entries: Any, registry: _IdRegistry) -> tuple[EducationEntry, ...]:
    entries: list[EducationEntry] = []
    for index, raw_entry in enumerate(_coerce_list(raw_entries)):
        if not isinstance(raw_entry, Mapping):
            continue
        institution = _as_text(raw_entry.get("institution"))
        location = _as_text(raw_entry.get("location"))
        degree = _as_text(raw_entry.get("degree"))
        date = _as_text(raw_entry.get("date"))
        entry_id = _entry_id(raw_entry, derive_legacy_id("education", institution, degree, date))
        path = f"education[{index}].id"
        registry.add(entry_id, path, path)
        entries.append(
            EducationEntry(
                id=entry_id,
                institution=institution,
                location=location,
                degree=degree,
                date=date,
                coursework=tuple(_as_text(item) for item in _coerce_list(raw_entry.get("coursework"))),
            )
        )
    return tuple(entries)


def _parse_experiences(raw_entries: Any, registry: _IdRegistry) -> tuple[ExperienceEntry, ...]:
    entries: list[ExperienceEntry] = []
    for index, raw_entry in enumerate(_coerce_list(raw_entries)):
        if not isinstance(raw_entry, Mapping):
            continue
        organization = _as_text(raw_entry.get("organization"))
        location = _as_text(raw_entry.get("location"))
        role = _as_text(raw_entry.get("role"))
        date = _as_text(raw_entry.get("date"))
        entry_id = _entry_id(raw_entry, derive_legacy_id("experience", organization, role, date))
        path = f"experiences[{index}].id"
        registry.add(entry_id, path, path)
        bullets = _parse_bullets(
            raw_entry.get("bullets"),
            owner_id=entry_id,
            owner_type="experience",
            owner_path=f"experiences[{index}]",
            registry=registry,
        )
        entries.append(
            ExperienceEntry(
                id=entry_id,
                organization=organization,
                location=location,
                role=role,
                date=date,
                bullets=bullets,
            )
        )
    return tuple(entries)


def _parse_projects(raw_entries: Any, registry: _IdRegistry) -> tuple[ProjectEntry, ...]:
    entries: list[ProjectEntry] = []
    for index, raw_entry in enumerate(_coerce_list(raw_entries)):
        if not isinstance(raw_entry, Mapping):
            continue
        name = _as_text(raw_entry.get("name"))
        technologies = _as_text(raw_entry.get("technologies"))
        date = _as_text(raw_entry.get("date"))
        entry_id = _entry_id(raw_entry, derive_legacy_id("project", name, date))
        path = f"projects[{index}].id"
        registry.add(entry_id, path, path)
        bullets = _parse_bullets(
            raw_entry.get("bullets"),
            owner_id=entry_id,
            owner_type="project",
            owner_path=f"projects[{index}]",
            registry=registry,
        )
        entries.append(
            ProjectEntry(
                id=entry_id,
                name=name,
                technologies=technologies,
                date=date,
                bullets=bullets,
            )
        )
    return tuple(entries)


def _parse_bullets(
    raw_bullets: Any,
    *,
    owner_id: str,
    owner_type: str,
    owner_path: str,
    registry: _IdRegistry,
) -> tuple[Bullet, ...]:
    bullets: list[Bullet] = []
    for index, raw_bullet in enumerate(_coerce_list(raw_bullets), start=1):
        bullet_id = f"{owner_id}:bullet-{index}"
        if isinstance(raw_bullet, Mapping):
            text = _as_text(raw_bullet.get("text", raw_bullet.get("description", "")))
            if raw_bullet.get("id") is not None:
                bullet_id = normalize_id(raw_bullet.get("id"))
        else:
            text = _as_text(raw_bullet)
        path = f"{owner_path}.bullets[{index - 1}].id"
        registry.add(bullet_id, path, path)
        bullets.append(
            Bullet(
                id=bullet_id,
                text=text,
                owner_id=owner_id,
                owner_type=owner_type,  # type: ignore[arg-type]
                source_index=index,
            )
        )
    return tuple(bullets)


def _parse_skills(raw_skills: Any, registry: _IdRegistry) -> tuple[SkillGroup, ...]:
    if isinstance(raw_skills, Mapping):
        skill_items = raw_skills.items()
    elif isinstance(raw_skills, list):
        skill_items = [("skills", raw_skills)]
    else:
        return ()

    groups: list[SkillGroup] = []
    for group_index, (raw_group_id, raw_group_skills) in enumerate(skill_items):
        group_id = normalize_id(raw_group_id)
        if not group_id:
            group_id = f"skill_group_{group_index + 1}"
        group_path = f"skills.{group_id}"
        registry.add(group_id, group_path, group_path)
        skills: list[SkillItem] = []
        for skill_index, raw_skill in enumerate(_coerce_list(raw_group_skills)):
            if isinstance(raw_skill, Mapping):
                label = _as_text(raw_skill.get("label", raw_skill.get("name", raw_skill.get("value", ""))))
                skill_id = (
                    normalize_id(raw_skill.get("id"))
                    if raw_skill.get("id") is not None
                    else f"skill:{group_id}:{slugify(label)}"
                )
            else:
                label = _as_text(raw_skill)
                skill_id = f"skill:{group_id}:{slugify(label)}"
            skill_path = f"{group_path}[{skill_index}].id"
            registry.add(skill_id, skill_path, skill_path)
            skills.append(SkillItem(id=skill_id, label=label, group_id=group_id))
        groups.append(SkillGroup(id=group_id, label=_skill_group_label(group_id), skills=tuple(skills)))
    return tuple(groups)


def _skill_group_label(group_id: str) -> str:
    return group_id.replace("_", " ").title()
