"""Render a Selection of the Profile into Jake's-template LaTeX. Values are trusted TeX."""
from __future__ import annotations

from .profile import Contact, Profile
from .selection import Selection

SKILL_GROUP_LABELS = {
    "languages": "Languages",
    "frameworks_and_libraries": r"Frameworks \& Libraries",
    "databases_and_infrastructure": r"Databases \& Infrastructure",
    "platforms_and_systems": r"Platforms \& Systems",
}

_PREAMBLE = r"""\documentclass[letterpaper,11pt]{article}

\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\input{glyphtounicode}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

% Adjust margins
\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}

\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

% Sections formatting
\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

% Ensure generated pdf is machine readable/ATS parsable
\pdfgentounicode=1

%-------------------------
% Custom commands
\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}

\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
"""


def render_resume(profile: Profile, selection: Selection) -> str:
    parts = [_PREAMBLE, r"\begin{document}", "", *_heading(profile.contact)]
    if profile.education:
        parts += _education(profile)
    if selection.experiences:
        parts += _experiences(profile, selection)
    if selection.projects:
        parts += _projects(profile, selection)
    if selection.skills:
        parts += _skills(selection)
    parts += [r"\end{document}", ""]
    return "\n".join(parts)


def _display_url(url: str) -> str:
    return url.removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")


def _href(url: str, label: str) -> str:
    return rf"\href{{{url}}}{{\underline{{{label}}}}}"


def _heading(contact: Contact) -> list[str]:
    links = [contact.phone] if contact.phone else []
    if contact.email:
        links.append(_href(f"mailto:{contact.email}", contact.email))
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
    return lines + [r"  \resumeSubHeadingListEnd", ""]


def _bullet_items(bullets: dict[str, str], picked: tuple[str, ...]) -> list[str]:
    lines = [r"      \resumeItemListStart"]
    lines += [rf"        \resumeItem{{{bullets[slug]}}}" for slug in picked if slug in bullets]
    return lines + [r"      \resumeItemListEnd"]


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
    return lines + [r"  \resumeSubHeadingListEnd", ""]


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
    return lines + [r"  \resumeSubHeadingListEnd", ""]


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
