from __future__ import annotations

from collections.abc import Iterable

from .models import (
    Contact,
    EducationEntry,
    RenderExperience,
    RenderModel,
    RenderProject,
    SkillGroup,
    TemplateSpec,
)


RENDERER_VERSION = "jakes-resume-tex-renderer-v1"

_SPECIAL_CHARS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

_UNICODE_CHARS = {
    "\u00a0": " ",
    "\u00b5": r"\ensuremath{\mu}",
    "\u03bc": r"\ensuremath{\mu}",
    "\u2013": "--",
    "\u2014": "---",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": "``",
    "\u201d": "''",
    "\u2026": "...",
}

_SKILL_GROUP_LABELS = {
    "languages": "Languages",
    "frameworks_and_libraries": r"Frameworks \& Libraries",
    "databases_and_infrastructure": r"Databases \& Infrastructure",
    "platforms_and_systems": r"Platforms \& Systems",
}


def escape_latex(value: object) -> str:
    """Escape canonical/user text for use as LaTeX text content."""
    if value is None:
        return ""
    return "".join(_SPECIAL_CHARS.get(char, _UNICODE_CHARS.get(char, char)) for char in str(value))


def render_tex(render_model: RenderModel, template_spec: TemplateSpec) -> str:
    if render_model.document_type != template_spec.document_type:
        raise ValueError(
            "RenderModel document_type "
            f"{render_model.document_type!r} does not match template {template_spec.document_type!r}."
        )
    if render_model.template_id != template_spec.id:
        raise ValueError(
            f"RenderModel template_id {render_model.template_id!r} does not match template {template_spec.id!r}."
        )
    if template_spec.document_type != "resume" or template_spec.id != "jakes_resume":
        raise NotImplementedError(f"No TeX renderer is registered for template {template_spec.id!r}.")

    return render_jakes_resume_tex(render_model, template_spec)


class TexRenderer:
    version = RENDERER_VERSION

    @staticmethod
    def render(render_model: RenderModel, template_spec: TemplateSpec) -> str:
        return render_tex(render_model, template_spec)


def render_jakes_resume_tex(render_model: RenderModel, template_spec: TemplateSpec) -> str:
    lines = _jakes_preamble_lines()
    lines.extend(
        [
            r"",
            r"%-------------------------------------------",
            r"%%%%%%  RESUME STARTS HERE  %%%%%%%%%%%%%%%%%%%%%%%%%%%%",
            r"",
            r"\begin{document}",
            r"",
            r"%----------HEADING----------",
        ]
    )
    lines.extend(_render_contact(render_model.contact))
    lines.append(r"")

    known_sections = set(template_spec.section_order)
    for section in render_model.sections:
        if section not in known_sections:
            raise ValueError(f"Unknown section {section!r} for template {template_spec.id!r}.")
        if section == "education" and render_model.education:
            lines.extend(_render_education(render_model.education))
        elif section == "experience" and render_model.experiences:
            lines.extend(_render_experience(render_model.experiences))
        elif section == "projects" and render_model.projects:
            lines.extend(_render_projects(render_model.projects))
        elif section == "technical_skills":
            skill_lines = _skill_group_lines(render_model.skills, template_spec)
            if skill_lines:
                lines.extend(_render_skills(skill_lines))

    lines.extend(
        [
            r"%-------------------------------------------",
            r"\end{document}",
        ]
    )
    return "\n".join(lines) + "\n"


def _jakes_preamble_lines() -> list[str]:
    return [
        r"\documentclass[letterpaper,11pt]{article}",
        r"",
        r"\usepackage{latexsym}",
        r"\usepackage[empty]{fullpage}",
        r"\usepackage{titlesec}",
        r"\usepackage{marvosym}",
        r"\usepackage[usenames,dvipsnames]{color}",
        r"\usepackage{verbatim}",
        r"\usepackage{enumitem}",
        r"\usepackage[hidelinks]{hyperref}",
        r"\usepackage{fancyhdr}",
        r"\usepackage[english]{babel}",
        r"\usepackage{tabularx}",
        r"\input{glyphtounicode}",
        r"",
        r"\pagestyle{fancy}",
        r"\fancyhf{} % clear all header and footer fields",
        r"\fancyfoot{}",
        r"\renewcommand{\headrulewidth}{0pt}",
        r"\renewcommand{\footrulewidth}{0pt}",
        r"",
        r"% Adjust margins",
        r"\addtolength{\oddsidemargin}{-0.5in}",
        r"\addtolength{\evensidemargin}{-0.5in}",
        r"\addtolength{\textwidth}{1in}",
        r"\addtolength{\topmargin}{-.5in}",
        r"\addtolength{\textheight}{1.0in}",
        r"",
        r"\urlstyle{same}",
        r"",
        r"\raggedbottom",
        r"\raggedright",
        r"\setlength{\tabcolsep}{0in}",
        r"",
        r"% Sections formatting",
        r"\titleformat{\section}{",
        r"  \vspace{-4pt}\scshape\raggedright\large",
        r"}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]",
        r"",
        r"% Ensure that generate pdf is machine readable/ATS parsable",
        r"\pdfgentounicode=1",
        r"",
        r"%-------------------------",
        r"% Custom commands",
        r"\newcommand{\resumeItem}[1]{",
        r"  \item\small{",
        r"    {#1 \vspace{-2pt}}",
        r"  }",
        r"}",
        r"",
        r"\newcommand{\resumeSubheading}[4]{",
        r"  \vspace{-2pt}\item",
        r"    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}",
        r"      \textbf{#1} & #2 \\",
        r"      \textit{\small#3} & \textit{\small #4} \\",
        r"    \end{tabular*}\vspace{-7pt}",
        r"}",
        r"",
        r"\newcommand{\resumeSubSubheading}[2]{",
        r"    \item",
        r"    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}",
        r"      \textit{\small#1} & \textit{\small #2} \\",
        r"    \end{tabular*}\vspace{-7pt}",
        r"}",
        r"",
        r"\newcommand{\resumeProjectHeading}[2]{",
        r"    \item",
        r"    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}",
        r"      \small#1 & #2 \\",
        r"    \end{tabular*}\vspace{-7pt}",
        r"}",
        r"",
        r"\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}",
        r"",
        r"\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}",
        r"",
        (
            r"\newcommand{\resumeSubHeadingListStart}"
            r"{\begin{itemize}[leftmargin=0.15in, label={}]}"
        ),
        r"\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}",
        r"\newcommand{\resumeItemListStart}{\begin{itemize}}",
        r"\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}",
    ]


def _render_contact(contact: Contact) -> list[str]:
    lines = [
        r"\begin{center}",
        rf"    \textbf{{\Huge \scshape {escape_latex(contact.name)}}} \\ \vspace{{1pt}}",
    ]
    contact_parts = _contact_parts(contact)
    if contact_parts:
        lines.append("    \\small " + " $|$ ".join(contact_parts))
    lines.append(r"\end{center}")
    return lines


def _contact_parts(contact: Contact) -> list[str]:
    parts: list[str] = []
    if contact.phone:
        parts.append(escape_latex(contact.phone))
    if contact.email:
        email_url = "mailto:" + contact.email
        parts.append(_href(email_url, contact.email))
    if contact.website:
        parts.append(_href(contact.website, _display_url(contact.website)))
    if contact.linkedin:
        parts.append(_href(contact.linkedin, _social_display(contact.linkedin, "linkedin.com/in/")))
    if contact.github:
        parts.append(_href(contact.github, _social_display(contact.github, "github.com/")))
    return parts


def _href(url: str, label: str) -> str:
    return rf"\href{{{escape_latex(url)}}}{{\underline{{{escape_latex(label)}}}}}"


def _display_url(url: str) -> str:
    display = url.removeprefix("https://").removeprefix("http://").removeprefix("www.")
    return display.rstrip("/")


def _social_display(url: str, prefix: str) -> str:
    display = _display_url(url)
    for host_prefix in (prefix, "www." + prefix):
        if display.startswith(host_prefix):
            return prefix + display[len(host_prefix) :].strip("/")
    return display


def _render_education(education: Iterable[EducationEntry]) -> list[str]:
    lines = [
        r"%-----------EDUCATION-----------",
        r"\section{Education}",
        r"  \resumeSubHeadingListStart",
    ]
    for entry in education:
        lines.extend(
            [
                r"    \resumeSubheading",
                rf"      {{{escape_latex(entry.institution)}}}{{{escape_latex(entry.location)}}}",
                rf"      {{{escape_latex(entry.degree)}}}{{{escape_latex(entry.date)}}}",
            ]
        )
        if entry.coursework:
            lines.extend(
                [
                    r"      \resumeItemListStart",
                    rf"        \resumeItem{{Relevant Coursework: {escape_latex(', '.join(entry.coursework))}.}}",
                    r"      \resumeItemListEnd",
                ]
            )
    lines.extend(
        [
            r"  \resumeSubHeadingListEnd",
            r"",
        ]
    )
    return lines


def _render_experience(experiences: Iterable[RenderExperience]) -> list[str]:
    lines = [
        r"%-----------EXPERIENCE-----------",
        r"\section{Experience}",
        r"  \resumeSubHeadingListStart",
        r"",
    ]
    for experience in experiences:
        entry = experience.entry
        lines.extend(
            [
                r"    \resumeSubheading",
                rf"      {{{escape_latex(entry.role)}}}{{{escape_latex(entry.date)}}}",
                rf"      {{{escape_latex(entry.organization)}}}{{{escape_latex(entry.location)}}}",
            ]
        )
        if experience.bullets:
            lines.append(r"      \resumeItemListStart")
            for bullet in experience.bullets:
                lines.append(rf"        \resumeItem{{{escape_latex(bullet.text)}}}")
            lines.append(r"      \resumeItemListEnd")
        lines.append(r"")
    lines.extend(
        [
            r"  \resumeSubHeadingListEnd",
            r"",
        ]
    )
    return lines


def _render_projects(projects: Iterable[RenderProject]) -> list[str]:
    lines = [
        r"%-----------PROJECTS-----------",
        r"\section{Projects}",
        r"  \resumeSubHeadingListStart",
        r"",
    ]
    for project in projects:
        entry = project.entry
        technologies = rf" $|$ \emph{{{escape_latex(entry.technologies)}}}" if entry.technologies else ""
        lines.extend(
            [
                r"    \resumeProjectHeading",
                rf"      {{\textbf{{{escape_latex(entry.name)}}}{technologies}}}{{{escape_latex(entry.date)}}}",
            ]
        )
        if project.bullets:
            lines.append(r"      \resumeItemListStart")
            for bullet in project.bullets:
                lines.append(rf"        \resumeItem{{{escape_latex(bullet.text)}}}")
            lines.append(r"      \resumeItemListEnd")
        lines.append(r"")
    lines.extend(
        [
            r"  \resumeSubHeadingListEnd",
            r"",
        ]
    )
    return lines


def _skill_group_lines(skills: Iterable[SkillGroup], template_spec: TemplateSpec) -> list[str]:
    skill_groups = list(skills)
    groups_by_id = {group.id: group for group in skill_groups}
    ordered_ids = [group_id for group_id in template_spec.skill_group_order if group_id in groups_by_id]
    ordered_id_set = set(ordered_ids)
    ordered_ids.extend(group.id for group in skill_groups if group.id not in ordered_id_set)

    lines: list[str] = []
    for group_id in ordered_ids:
        group = groups_by_id[group_id]
        if not group.skills:
            continue
        label = _SKILL_GROUP_LABELS.get(group.id, escape_latex(group.label))
        values = escape_latex(", ".join(skill.label for skill in group.skills))
        lines.append(rf"     \textbf{{{label}}}{{: {values}}}")
    return lines


def _render_skills(skill_lines: list[str]) -> list[str]:
    lines = [
        r"%-----------TECHNICAL SKILLS-----------",
        r"\section{Technical Skills}",
        r" \begin{itemize}[leftmargin=0.15in, label={}]",
        r"    \small{\item{",
    ]
    for index, line in enumerate(skill_lines):
        suffix = r" \\" if index < len(skill_lines) - 1 else ""
        lines.append(line + suffix)
    lines.extend(
        [
            r"    }}",
            r" \end{itemize}",
            r"",
        ]
    )
    return lines
