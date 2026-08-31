"""Render a Selection of the Profile into Jake's-template LaTeX. Values are trusted TeX."""

from __future__ import annotations

from pathlib import Path

from .profile import REQUIRED_CONTACT_FIELDS, Contact, Profile
from .selection import Selection

SKILL_GROUP_LABELS = {
    "languages": "Languages",
    "frameworks_and_libraries": r"Frameworks \& Libraries",
    "databases_and_infrastructure": r"Databases \& Infrastructure",
    "platforms_and_systems": r"Platforms \& Systems",
}

DEFAULT_TEMPLATE_PATH = Path("source_of_truth_resume.tex")
_DOCUMENT_START = r"\begin{document}"


def render_resume(
    profile: Profile,
    selection: Selection,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> str:
    template_path = Path(template_path)
    if not template_path.is_file():
        raise FileNotFoundError(f"Resume template not found: {template_path}")
    template = template_path.read_text(encoding="utf-8")
    preamble, document_start, _ = template.partition(_DOCUMENT_START)
    if not document_start:
        raise ValueError(f"Resume template {template_path} has no {_DOCUMENT_START} marker.")

    parts = [_DOCUMENT_START, "", *_heading(profile.contact)]
    if profile.education:
        parts += _education(profile)
    if selection.experiences:
        parts += _experiences(profile, selection)
    if selection.projects:
        parts += _projects(profile, selection)
    if selection.skills:
        parts += _skills(selection)
    parts += [r"\end{document}", ""]
    return preamble + "\n".join(parts)


def _display_url(url: str) -> str:
    return url.removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")


def _href(url: str, label: str) -> str:
    return rf"\href{{{url}}}{{\underline{{{label}}}}}"


def _heading(contact: Contact) -> list[str]:
    """Render the contact header.

    ``name``, ``email`` and ``phone`` are mandatory and a missing one is a hard error:
    dropping a field silently produced a header a recruiter cannot answer, and no downstream
    gate could tell, because every gate compares the PDF against the profile that rendered
    it. ``website``, ``linkedin`` and ``github`` stay optional and are simply omitted.
    """
    for field_name in REQUIRED_CONTACT_FIELDS:
        if not getattr(contact, field_name, "").strip():
            raise ValueError(
                f"Cannot render a resume header: contact.{field_name} is empty. A resume "
                f"missing it cannot be answered; fix profile.json (recover it with "
                f"`uv run worksisyphus db export-profile --force`) rather than shipping "
                f"a header without it."
            )

    links = [contact.phone, _href(f"mailto:{contact.email}", contact.email)]
    for url in (contact.website, contact.linkedin, contact.github):
        if url:
            links.append(_href(url, _display_url(url)))
    return [
        r"\begin{center}",
        rf"    \textbf{{\Huge \scshape {contact.name}}} \\ \vspace{{1pt}}",
        "    \\small " + " $|$ ".join(links),
        r"\end{center}",
        "",
    ]


def _education(profile: Profile) -> list[str]:
    lines = [r"\section{Education}", r"  \resumeSubHeadingListStart"]
    for entry in profile.education:
        lines += [
            r"    \resumeSubheading",
            rf"      {{{entry.institution}}}{{{entry.location}}}",
            rf"      {{{entry.degree}}}{{{entry.date}}}",
        ]
        if entry.coursework:
            lines += [
                r"      \resumeItemListStart",
                rf"        \resumeItem{{Relevant Coursework: {', '.join(entry.coursework)}.}}",
                r"      \resumeItemListEnd",
            ]
    return [*lines, r"  \resumeSubHeadingListEnd", ""]


def _bullet_items(bullets: dict[str, str], picked: tuple[str, ...]) -> list[str]:
    lines = [r"      \resumeItemListStart"]
    lines += [rf"        \resumeItem{{{bullets[slug]}}}" for slug in picked if slug in bullets]
    return [*lines, r"      \resumeItemListEnd"]


def _experiences(profile: Profile, selection: Selection) -> list[str]:
    lines = [r"\section{Experience}", r"  \resumeSubHeadingListStart", ""]
    for pick in selection.experiences:
        entry = profile.experiences[pick.id]
        lines += [
            r"    \resumeSubheading",
            rf"      {{{entry.role}}}{{{entry.date}}}",
            rf"      {{{entry.org}}}{{{entry.location}}}",
            *_bullet_items(entry.bullets, pick.bullets),
            "",
        ]
    return [*lines, r"  \resumeSubHeadingListEnd", ""]


def _projects(profile: Profile, selection: Selection) -> list[str]:
    lines = [r"\section{Projects}", r"  \resumeSubHeadingListStart", ""]
    for pick in selection.projects:
        entry = profile.projects[pick.id]
        tech = rf" $|$ \emph{{{entry.tech}}}" if entry.tech else ""
        lines += [
            r"    \resumeProjectHeading",
            rf"      {{\textbf{{{entry.name}}}{tech}}}{{{entry.date}}}",
            *_bullet_items(entry.bullets, pick.bullets),
            "",
        ]
    return [*lines, r"  \resumeSubHeadingListEnd", ""]


def _skills(selection: Selection) -> list[str]:
    rows = [
        rf"     \textbf{{{SKILL_GROUP_LABELS.get(group, group)}}}{{: {', '.join(items)}}}"
        for group, items in selection.skills.items()
        if items
    ]
    body = [row + (r" \\" if i < len(rows) - 1 else "") for i, row in enumerate(rows)]
    return [
        r"\section{Technical Skills}",
        r" \begin{itemize}[leftmargin=0.15in, label={}]",
        r"    \small{\item{",
        *body,
        r"    }}",
        r" \end{itemize}",
        "",
    ]
