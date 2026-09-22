"""Render a Selection of the Profile into Jake's-template LaTeX. Values are trusted TeX."""

from __future__ import annotations

from pathlib import Path

from ..domain.models import (
    DEFAULT_COMPILER_CONFIG,
    REQUIRED_CONTACT_FIELDS,
    CompilerConfig,
    Contact,
    CourseworkMode,
    Profile,
    Selection,
    validate_contact,
)

SKILL_GROUP_LABELS = {
    "languages": "Languages",
    "frameworks_and_libraries": r"Frameworks \& Libraries",
    "databases_and_infrastructure": r"Databases \& Infrastructure",
}

DEFAULT_TEMPLATE_PATH = Path("source_of_truth_resume.tex")
_DOCUMENT_START = r"\begin{document}"


def render_resume(
    profile: Profile,
    selection: Selection,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
    config: CompilerConfig = DEFAULT_COMPILER_CONFIG,
) -> str:
    """Render a selection into LaTeX, refusing outright to render an undeliverable contact."""
    validate_contact(profile.contact)
    template_path = Path(template_path)
    if not template_path.is_file():
        raise FileNotFoundError(f"Resume template not found: {template_path}")
    template = template_path.read_text(encoding="utf-8")
    preamble, document_start, _ = template.partition(_DOCUMENT_START)
    if not document_start:
        raise ValueError(f"Resume template {template_path} has no {_DOCUMENT_START} marker.")

    parts = [_DOCUMENT_START, "", *_heading(profile.contact, config=config)]
    if profile.education:
        parts += _education(profile, config=config)
    if selection.experiences:
        parts += _experiences(profile, selection)
    if selection.projects:
        parts += _projects(profile, selection)
    if selection.skills:
        parts += _skills(selection, config=config)
    parts += [r"\end{document}", ""]
    return preamble + "\n".join(parts)


def _display_url(url: str) -> str:
    return url.removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")


def _href(url: str, label: str) -> str:
    return rf"\href{{{url}}}{{\underline{{{label}}}}}"


def _heading(contact: Contact, config: CompilerConfig = DEFAULT_COMPILER_CONFIG) -> list[str]:
    """Render the contact header."""
    for field_name in REQUIRED_CONTACT_FIELDS:
        if not getattr(contact, field_name, "").strip():
            raise ValueError(
                f"Cannot render a resume header: contact.{field_name} is empty. A resume "
                f"missing it cannot be answered; fix profile.json (recover it with "
                f"`uv run worksisyphus db export-profile --force`) rather than shipping "
                f"a header without it."
            )

    if config.clickable_links:
        links = [contact.phone, _href(f"mailto:{contact.email}", contact.email)]
        for url in (contact.website, contact.linkedin, contact.github):
            if url:
                links.append(_href(url, _display_url(url)))
    else:
        links = [contact.phone, contact.email]
        for url in (contact.website, contact.linkedin, contact.github):
            if url:
                links.append(_display_url(url))

    return [
        r"\begin{center}",
        rf"    \textbf{{\Huge \scshape {contact.name}}} \\ \vspace{{1pt}}",
        "    \\small " + " $|$ ".join(links),
        r"\end{center}",
        "",
    ]


def _education(profile: Profile, config: CompilerConfig = DEFAULT_COMPILER_CONFIG) -> list[str]:
    lines = [r"\section{Education}", r"  \resumeSubHeadingListStart"]
    for entry in profile.education:
        location = entry.location if config.include_locations else ""
        degree_text = entry.degree
        if config.include_gpa and entry.gpa:
            degree_text = f"{degree_text} $|$ GPA: {entry.gpa}"

        lines += [
            r"    \resumeSubheading",
            rf"      {{{entry.institution}}}{{{location}}}",
            rf"      {{{degree_text}}}{{{entry.date}}}",
        ]
        if entry.coursework and config.coursework_mode != CourseworkMode.NONE:
            courses = entry.coursework
            if config.coursework_mode == CourseworkMode.CONDENSED and len(courses) > 4:
                courses = courses[:4]
            lines += [
                r"      \resumeItemListStart",
                rf"        \resumeItem{{Relevant Coursework: {', '.join(courses)}.}}",
                r"      \resumeItemListEnd",
            ]
    return [*lines, r"  \resumeSubHeadingListEnd", ""]


def _bullet_items(bullets: dict[str, str], picked: tuple[str, ...]) -> list[str]:
    lines = [r"      \resumeItemListStart"]
    for slug in picked:
        if slug not in bullets:
            raise ValueError(f"Unknown bullet slug '{slug}'; entry contains only {list(bullets.keys())}.")
        lines.append(rf"        \resumeItem{{{bullets[slug]}}}")
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


def _skills(selection: Selection, config: CompilerConfig = DEFAULT_COMPILER_CONFIG) -> list[str]:
    rows = []
    for group, items in selection.skills.items():
        if not items:
            continue
        if group not in SKILL_GROUP_LABELS:
            raise ValueError(
                f"Unknown skill group '{group}' has no display label in SKILL_GROUP_LABELS: "
                f"{list(SKILL_GROUP_LABELS.keys())}."
            )
        rows.append(rf"\textbf{{{SKILL_GROUP_LABELS[group]}}}{{: {', '.join(items)}}}")

    if not rows:
        return []

    if config.compact_skills:
        return [
            r"\section{Technical Skills}",
            r"  \begin{itemize}[leftmargin=0.15in, label={}]",
            r"    \small{\item{" + " $|$ ".join(rows) + r"}}",
            r"  \end{itemize}",
            "",
        ]

    body = [row + (r" \\" if i < len(rows) - 1 else "") for i, row in enumerate(rows)]
    return [
        r"\section{Technical Skills}",
        r"  \begin{itemize}[leftmargin=0.15in, label={}]",
        r"    \small{\item{",
        *body,
        r"    }}",
        r"  \end{itemize}",
        "",
    ]
