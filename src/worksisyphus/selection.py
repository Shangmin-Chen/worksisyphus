"""Selection of profile content for one resume, and the deterministic one-page trim order."""
from __future__ import annotations

from dataclasses import dataclass, replace

from .profile import Profile

MIN_BULLETS = 2


@dataclass(frozen=True)
class Pick:
    """One selected experience/project: 0-based index plus 0-based bullet indices."""

    index: int
    bullets: tuple[int, ...]


@dataclass(frozen=True)
class Selection:
    """Ranked selection (most relevant first) plus the Gemini-chosen output name."""

    name: str
    experiences: tuple[Pick, ...]
    projects: tuple[Pick, ...]
    skills: dict[str, tuple[str, ...]]


def full_selection(profile: Profile, name: str = "Simon_Chen_Resume_Compiled") -> Selection:
    """The canonical everything-included selection."""
    return Selection(
        name=name,
        experiences=tuple(Pick(i, tuple(range(len(e.bullets)))) for i, e in enumerate(profile.experiences)),
        projects=tuple(Pick(i, tuple(range(len(p.bullets)))) for i, p in enumerate(profile.projects)),
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

    for pick_list, field_name in ((selection.projects, "projects"), (selection.experiences[::-1], "experiences")):
        for pick in pick_list:
            if len(pick.bullets) > MIN_BULLETS:
                trimmed = replace(pick, bullets=pick.bullets[:-1])
                originals = getattr(selection, field_name)
                updated = tuple(trimmed if p is pick else p for p in originals)
                return replace(selection, **{field_name: updated})
    return None
