"""Selection of profile content for one resume, and the deterministic one-page trim order."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .profile import Profile

MIN_BULLETS = 2
TAILORED_NAME = "Simon_Chen_Resume"  # every employer-facing PDF gets this name; archives keep per-application copies


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


def full_selection(profile: Profile, name: str = "Simon_Chen_Resume_Compiled") -> Selection:
    """The canonical everything-included selection."""
    return Selection(
        name=name,
        experiences=tuple(Pick(slug, tuple(e.bullets)) for slug, e in profile.experiences.items()),
        projects=tuple(Pick(slug, tuple(p.bullets)) for slug, p in profile.projects.items()),
        skills=dict(profile.skills),
    )


def trim_step(selection: Selection) -> Selection | None:
    """Return the next-smaller selection, or None when nothing sensible is left to cut.

    Order: drop lowest-ranked projects down to one, then trim that project's
    bullets, then trim experience bullets starting from the lowest-ranked
    experience. Never goes below MIN_BULLETS per kept item.
    """
    if len(selection.projects) > 1:
        return replace(selection, projects=selection.projects[:-1])

    for pick_list, is_projects in ((selection.projects, True), (selection.experiences[::-1], False)):
        for pick in pick_list:
            if len(pick.bullets) > MIN_BULLETS:
                trimmed = replace(pick, bullets=pick.bullets[:-1])
                originals = selection.projects if is_projects else selection.experiences
                updated = tuple(trimmed if p is pick else p for p in originals)
                return replace(selection, projects=updated) if is_projects else replace(selection, experiences=updated)
    return None
