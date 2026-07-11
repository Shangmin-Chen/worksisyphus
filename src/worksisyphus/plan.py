"""Parse a hand-written plan file (JSON of slugs) into a validated Selection.

Plan format — order is rank (most relevant first), which drives the trim order:

    {
      "name": "bosch_swe_ii",
      "experiences": {"ezesports": "all", "reset-standard": ["water-waste-integration"]},
      "projects": ["persephone", "hermes-letters"],
      "skills": "all"
    }

Sections accept either an object (slug -> "all" | [bullet slugs]) or a plain
list of slugs (each meaning all bullets). "skills" is "all", an object
(group -> "all" | [items copied verbatim]), or omitted (meaning all).
Unknown slugs fail loudly; a plan can omit content, never invent it.
"""
from __future__ import annotations

import json
import re

from .profile import Experience, Profile, Project
from .selection import Pick, Selection


class PlanError(ValueError):
    """The plan references something the profile does not contain."""


def sanitize_name(raw: object) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(raw).lower()).strip("_")[:60]
    slug = slug or "tailored"
    return slug if slug.endswith("resume") else f"{slug}_resume"


def _parse_picks(raw: object, section: str, items: dict[str, Experience] | dict[str, Project]) -> tuple[Pick, ...]:
    if isinstance(raw, list):
        raw = {slug: "all" for slug in raw}
    if not isinstance(raw, dict):
        raise PlanError(f'"{section}" must be a list of slugs or an object of slug -> bullets.')
    picks: list[Pick] = []
    for slug, chosen in raw.items():
        entry = items.get(str(slug))
        if entry is None:
            raise PlanError(f"Unknown {section} slug {slug!r}. Run `worksisyphus index` to list valid slugs.")
        if chosen == "all":
            bullets = tuple(entry.bullets)
        elif isinstance(chosen, list):
            unknown = [b for b in chosen if b not in entry.bullets]
            if unknown:
                raise PlanError(f"Unknown bullet slug(s) {unknown!r} under {slug!r}.")
            bullets = tuple(dict.fromkeys(str(b) for b in chosen))
        else:
            raise PlanError(f'Bullets for {slug!r} must be "all" or a list of bullet slugs.')
        if not bullets:
            raise PlanError(f"No bullets selected for {slug!r}.")
        picks.append(Pick(id=entry.id, bullets=bullets))
    return tuple(picks)


def _parse_skills(raw: object, profile: Profile) -> dict[str, tuple[str, ...]]:
    if raw is None or raw == "all":
        return dict(profile.skills)
    if not isinstance(raw, dict):
        raise PlanError('"skills" must be "all" or an object of group -> "all" | [items].')
    skills: dict[str, tuple[str, ...]] = {}
    for group, items in raw.items():
        known = profile.skills.get(group)
        if known is None:
            raise PlanError(f"Unknown skill group {group!r}.")
        if items == "all":
            skills[group] = known
            continue
        if not isinstance(items, list):
            raise PlanError(f'Skills for {group!r} must be "all" or a list.')
        unknown = [item for item in items if item not in known]
        if unknown:
            raise PlanError(f"Unknown skill(s) {unknown!r} in group {group!r}; items must match the profile verbatim.")
        if items:
            skills[group] = tuple(dict.fromkeys(str(item) for item in items))
    return skills


def parse_plan(text: str, profile: Profile, default_name: str = "") -> Selection:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanError(f"Plan is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PlanError("Plan must be a JSON object.")
    unknown_keys = set(data) - {"name", "experiences", "projects", "skills"}
    if unknown_keys:
        raise PlanError(f"Unknown plan key(s): {sorted(unknown_keys)!r}.")
    experiences = _parse_picks(data.get("experiences", []), "experiences", profile.experiences)
    projects = _parse_picks(data.get("projects", []), "projects", profile.projects)
    if not experiences and not projects:
        raise PlanError("Plan selects no experiences and no projects.")
    return Selection(
        name=sanitize_name(data.get("name") or default_name),
        experiences=experiences,
        projects=projects,
        skills=_parse_skills(data.get("skills"), profile),
    )
