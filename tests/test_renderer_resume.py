from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus import build_render_model, get_template_spec, normalize_selection_plan, render_tex
from worksisyphus.profile import parse_canonical_profile


EXPECTED_TEX = r"""\documentclass[letterpaper,11pt]{article}

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
\fancyhf{} % clear all header and footer fields
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

% Ensure that generate pdf is machine readable/ATS parsable
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

\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}

\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

%-------------------------------------------
%%%%%%  RESUME STARTS HERE  %%%%%%%%%%%%%%%%%%%%%%%%%%%%

\begin{document}

%----------HEADING----------
\begin{center}
    \textbf{\Huge \scshape Ada Lovelace} \\ \vspace{1pt}
    \small 555-0100 $|$ \href{mailto:ada@example.com}{\underline{ada@example.com}} $|$ \href{https://ada.dev}{\underline{ada.dev}} $|$ \href{https://linkedin.com/in/ada}{\underline{linkedin.com/in/ada}} $|$ \href{https://github.com/ada}{\underline{github.com/ada}}
\end{center}

%-----------EDUCATION-----------
\section{Education}
  \resumeSubHeadingListStart
    \resumeSubheading
      {Analytical University}{London, UK}
      {B.S. in Computing}{May 2026}
      \resumeItemListStart
        \resumeItem{Relevant Coursework: Algorithms, Compilers.}
      \resumeItemListEnd
  \resumeSubHeadingListEnd

%-----------EXPERIENCE-----------
\section{Experience}
  \resumeSubHeadingListStart

    \resumeSubheading
      {Compiler Engineer}{Jan 2025 -- Present}
      {Difference Engine Co}{Remote}
      \resumeItemListStart
        \resumeItem{Built deterministic render pipeline.}
        \resumeItem{Shipped cache hits across jobs.}
      \resumeItemListEnd

  \resumeSubHeadingListEnd

%-----------PROJECTS-----------
\section{Projects}
  \resumeSubHeadingListStart

    \resumeProjectHeading
      {\textbf{Resume Compiler} $|$ \emph{Python, TeX}}{July 2026}
      \resumeItemListStart
        \resumeItem{Rendered trusted TeX from canonical IDs.}
      \resumeItemListEnd

  \resumeSubHeadingListEnd

%-----------TECHNICAL SKILLS-----------
\section{Technical Skills}
 \begin{itemize}[leftmargin=0.15in, label={}]
    \small{\item{
     \textbf{Languages}{: Python, C++} \\
     \textbf{Frameworks \& Libraries}{: unittest}
    }}
 \end{itemize}

%-------------------------------------------
\end{document}
"""


def build_sample_render_model():
    raw_profile = {
        "contact": {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "555-0100",
            "website": "https://ada.dev",
            "github": "https://github.com/ada",
            "linkedin": "https://linkedin.com/in/ada",
        },
        "education": [
            {
                "institution": "Analytical University",
                "location": "London, UK",
                "degree": "B.S. in Computing",
                "date": "May 2026",
                "coursework": ["Algorithms", "Compilers"],
            }
        ],
        "experiences": [
            {
                "organization": "Difference Engine Co",
                "location": "Remote",
                "role": "Compiler Engineer",
                "date": "Jan 2025 -- Present",
                "bullets": ["Built deterministic render pipeline.", "Shipped cache hits across jobs."],
            }
        ],
        "projects": [
            {
                "name": "Resume Compiler",
                "technologies": "Python, TeX",
                "date": "July 2026",
                "bullets": ["Rendered trusted TeX from canonical IDs."],
            }
        ],
        "skills": {
            "languages": ["Python", "C++"],
            "frameworks_and_libraries": ["unittest"],
            "databases_and_infrastructure": [],
        },
    }
    profile = parse_canonical_profile(raw_profile)
    template = get_template_spec("jakes_resume")
    experience = profile.experiences[0]
    project = profile.projects[0]
    languages = profile.skill_groups_by_id()["languages"]
    frameworks = profile.skill_groups_by_id()["frameworks_and_libraries"]
    plan = normalize_selection_plan(
        {
            "document_type": "resume",
            "template_id": "jakes_resume",
            "sections": ["education", "experience", "projects", "technical_skills"],
            "education_ids": [profile.education[0].id],
            "experience_ids": [experience.id],
            "project_ids": [project.id],
            "bullet_ids_by_item": {
                experience.id: [bullet.id for bullet in experience.bullets],
                project.id: [project.bullets[0].id],
            },
            "skill_ids_by_group": {
                "languages": [skill.id for skill in languages.skills],
                "frameworks_and_libraries": [frameworks.skills[0].id],
                "databases_and_infrastructure": [],
            },
            "rationale": "This must not render.",
        },
        profile=profile,
        template_spec=template,
    )
    return build_render_model(profile=profile, selection_plan=plan, template_spec=template), template


class ResumeRendererTests(unittest.TestCase):
    def test_jakes_resume_tex_snapshot_is_byte_stable(self) -> None:
        render_model, template = build_sample_render_model()

        first = render_tex(render_model, template)
        second = render_tex(render_model, template)

        self.assertEqual(first, EXPECTED_TEX)
        self.assertEqual(first.encode("utf-8"), second.encode("utf-8"))

    def test_resume_sub_item_command_uses_resume_item(self) -> None:
        render_model, template = build_sample_render_model()
        rendered = render_tex(render_model, template)

        self.assertIn(
            r"\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}",
            rendered,
        )
        self.assertNotIn(
            r"\newcommand{\resumeSubItem}[1]{\resumeSubItem{#1}\vspace{-4pt}}",
            rendered,
        )

    def test_experience_heading_uses_role_date_then_organization_location(self) -> None:
        render_model, template = build_sample_render_model()
        rendered = render_tex(render_model, template)

        self.assertIn(
            "\n    \\resumeSubheading\n"
            "      {Compiler Engineer}{Jan 2025 -- Present}\n"
            "      {Difference Engine Co}{Remote}\n",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
