from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def tex_escape(text: str) -> str:
    if not isinstance(text, str):
        return str(text)
    
    # Escape LaTeX special characters
    replacements = {
        "\\": "\\textbackslash{}",
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "_": "\\_",
        "{": "\\{",
        "}": "\\}",
        "~": "\\textasciitilde{}",
        "^": "\\textasciicircum{}",
        "μ": "$\\mu$",
    }
    
    result = text
    # Escape backslashes first, then others
    result = result.replace("\\", "\\textbackslash{}")
    for char, replacement in replacements.items():
        if char != "\\":
            result = result.replace(char, replacement)
            
    # Clean up math symbols like ~ used for approximation
    result = result.replace("\\textasciitilde{}", "$\\sim$")
    return result


def generate_latex_resume(resume_data: dict[str, Any], contact_info: dict[str, Any]) -> str:
    name = contact_info.get("name", "Name")
    email = contact_info.get("email", "")
    phone = contact_info.get("phone", "")
    website = contact_info.get("website", "")
    github = contact_info.get("github", "")
    linkedin = contact_info.get("linkedin", "")

    lines = []
    
    lines.append(r"\documentclass[letterpaper,11pt]{article}")
    lines.append("")
    lines.append(r"\usepackage{latexsym}")
    lines.append(r"\usepackage[empty]{fullpage}")
    lines.append(r"\usepackage{titlesec}")
    lines.append(r"\usepackage{marvosym}")
    lines.append(r"\usepackage[usenames,dvipsnames]{color}")
    lines.append(r"\usepackage{verbatim}")
    lines.append(r"\usepackage{enumitem}")
    lines.append(r"\usepackage[hidelinks]{hyperref}")
    lines.append(r"\usepackage{fancyhdr}")
    lines.append(r"\usepackage[english]{babel}")
    lines.append(r"\usepackage{tabularx}")
    lines.append(r"\input{glyphtounicode}")
    lines.append("")
    lines.append(r"\pagestyle{fancy}")
    lines.append(r"\fancyhf{} % clear all header and footer fields")
    lines.append(r"\fancyfoot{}")
    lines.append(r"\renewcommand{\headrulewidth}{0pt}")
    lines.append(r"\renewcommand{\footrulewidth}{0pt}")
    lines.append("")
    # Adjust margins
    lines.append(r"\addtolength{\oddsidemargin}{-0.5in}")
    lines.append(r"\addtolength{\evensidemargin}{-0.5in}")
    lines.append(r"\addtolength{\textwidth}{1in}")
    lines.append(r"\addtolength{\topmargin}{-.5in}")
    lines.append(r"\addtolength{\textheight}{1.0in}")
    lines.append("")
    lines.append(r"\urlstyle{same}")
    lines.append("")
    lines.append(r"\raggedbottom")
    lines.append(r"\raggedright")
    lines.append(r"\setlength{\tabcolsep}{0in}")
    lines.append("")
    # Sections formatting
    lines.append(r"\titleformat{\section}{")
    lines.append(r"  \vspace{-10pt}\scshape\raggedright\large")
    lines.append(r"}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]")
    lines.append("")
    # Ensure that generate pdf is machine readable/ATS parsable
    lines.append(r"\pdfgentounicode=1")
    lines.append("")
    # Custom commands
    lines.append(r"\newcommand{\resumeItem}[1]{")
    lines.append(r"  \item\small{")
    lines.append(r"    {#1 \vspace{-2pt}}")
    lines.append(r"  }")
    lines.append(r"}")
    lines.append("")
    lines.append(r"\newcommand{\resumeSubheading}[4]{")
    lines.append(r"  \vspace{-2pt}\item")
    lines.append(r"    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}")
    lines.append(r"      \textbf{#1} & #2 \\")
    lines.append(r"      \textit{\small#3} & \textit{\small #4} \\")
    lines.append(r"    \end{tabular*}\vspace{-7pt}")
    lines.append(r"}")
    lines.append("")
    lines.append(r"\newcommand{\resumeSubSubheading}[2]{")
    lines.append(r"    \item")
    lines.append(r"    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}")
    lines.append(r"      \textit{\small#1} & \textit{\small #2} \\")
    lines.append(r"    \end{tabular*}\vspace{-7pt}")
    lines.append(r"}")
    lines.append("")
    lines.append(r"\newcommand{\resumeProjectHeading}[2]{")
    lines.append(r"    \item")
    lines.append(r"    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}")
    lines.append(r"      \small#1 & #2 \\")
    lines.append(r"    \end{tabular*}\vspace{-7pt}")
    lines.append(r"}")
    lines.append("")
    lines.append(r"\newcommand{\resumeSubItem}[1]{\resumeSubItem{#1}\vspace{-4pt}}")
    lines.append("")
    lines.append(r"\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}")
    lines.append("")
    lines.append(r"\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}")
    lines.append(r"\newcommand{\resumeSubHeadingListEnd}{\end{itemize}\vspace{-8pt}}")
    lines.append(r"\newcommand{\resumeItemListStart}{\begin{itemize}}")
    lines.append(r"\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}")
    lines.append("")
    lines.append(r"\begin{document}")
    lines.append("")
    
    # Heading block
    lines.append(r"\begin{center}")
    lines.append(rf"    \textbf{{\Huge \scshape {tex_escape(name)}}} \\ \vspace{{1pt}}")
    
    contact_parts = []
    if phone:
        contact_parts.append(tex_escape(phone))
    if email:
        contact_parts.append(rf"\href{{mailto:{email}}}{{\underline{{{tex_escape(email)}}}}}")
    if website:
        display_web = website.replace("https://", "").replace("http://", "")
        contact_parts.append(rf"\href{{{website}}}{{\underline{{{tex_escape(display_web)}}}}}")
    if linkedin:
        display_li = linkedin.replace("https://www.linkedin.com/in/", "").replace("https://linkedin.com/in/", "")
        contact_parts.append(rf"\href{{{linkedin}}}{{\underline{{linkedin.com/in/{tex_escape(display_li)}}}}}")
    if github:
        display_gh = github.replace("https://github.com/", "").replace("https://www.github.com/", "")
        contact_parts.append(rf"\href{{{github}}}{{\underline{{github.com/{tex_escape(display_gh)}}}}}")
        
    lines.append("    \\small " + " $|$ ".join(contact_parts))
    lines.append(r"\end{center}")
    lines.append("")

    # Education
    education = resume_data.get("education", [])
    if education:
        lines.append(r"%-----------EDUCATION-----------")
        lines.append(r"\section{Education}")
        lines.append(r"  \resumeSubHeadingListStart")
        for edu in education:
            inst = edu.get("institution", "")
            loc = edu.get("location", "")
            deg = edu.get("degree", "")
            date = edu.get("date", "")
            lines.append(f"    \\resumeSubheading")
            lines.append(f"      {{{tex_escape(inst)}}}{{{tex_escape(loc)}}}")
            lines.append(f"      {{{tex_escape(deg)}}}{{{tex_escape(date)}}}")
            
            coursework = edu.get("coursework", [])
            if coursework:
                lines.append(r"      \resumeItemListStart")
                lines.append(f"        \\resumeItem{{Relevant Coursework: {tex_escape(', '.join(coursework))}.}}")
                lines.append(r"      \resumeItemListEnd")
        lines.append(r"  \resumeSubHeadingListEnd")
        lines.append("")

    # Experience
    experiences = resume_data.get("experiences", [])
    if experiences:
        lines.append(r"%-----------EXPERIENCE-----------")
        lines.append(r"\section{Experience}")
        lines.append(r"  \resumeSubHeadingListStart")
        for exp in experiences:
            org = exp.get("organization", "")
            loc = exp.get("location", "")
            role = exp.get("role", "")
            date = exp.get("date", "")
            lines.append(f"    \\resumeSubheading")
            lines.append(f"      {{{tex_escape(role)}}}{{{tex_escape(date)}}}")
            lines.append(f"      {{{tex_escape(org)}}}{{{tex_escape(loc)}}}")
            lines.append(r"      \resumeItemListStart")
            for bullet in exp.get("bullets", []):
                lines.append(f"        \\resumeItem{{{tex_escape(bullet)}}}")
            lines.append(r"      \resumeItemListEnd")
        lines.append(r"  \resumeSubHeadingListEnd")
        lines.append("")

    # Projects
    projects = resume_data.get("projects", [])
    if projects:
        lines.append(r"%-----------PROJECTS-----------")
        lines.append(r"\section{Projects}")
        lines.append(r"  \resumeSubHeadingListStart")
        for proj in projects:
            p_name = proj.get("name", "")
            tech = proj.get("technologies", "")
            date = proj.get("date", "")
            tech_formatted = rf" $|$ \emph{{{tex_escape(tech)}}}" if tech else ""
            lines.append(f"    \\resumeProjectHeading")
            lines.append(f"      {{\\textbf{{{tex_escape(p_name)}}}{tech_formatted}}}{{{tex_escape(date)}}}")
            lines.append(r"      \resumeItemListStart")
            for bullet in proj.get("bullets", []):
                lines.append(f"        \\resumeItem{{{tex_escape(bullet)}}}")
            lines.append(r"      \resumeItemListEnd")
        lines.append(r"  \resumeSubHeadingListEnd")
        lines.append("")

    # Skills
    skills = resume_data.get("skills", {})
    if skills:
        lines.append(r"%-----------TECHNICAL SKILLS-----------")
        lines.append(r"\section{Technical Skills}")
        lines.append(r" \begin{itemize}[leftmargin=0.15in, label={}]")
        lines.append(r"    \small{\item{")
        
        skills_lines = []
        if "languages" in skills:
            skills_lines.append(rf"\textbf{{Languages}}{{: {tex_escape(', '.join(skills['languages']))}}}")
        if "frameworks_and_libraries" in skills:
            skills_lines.append(rf"\textbf{{Frameworks \& Libraries}}{{: {tex_escape(', '.join(skills['frameworks_and_libraries']))}}}")
        if "databases_and_infrastructure" in skills:
            skills_lines.append(rf"\textbf{{Databases \& Infrastructure}}{{: {tex_escape(', '.join(skills['databases_and_infrastructure']))}}}")
        if "platforms_and_systems" in skills:
            skills_lines.append(rf"\textbf{{Platforms \& Systems}}{{: {tex_escape(', '.join(skills['platforms_and_systems']))}}}")
        
        if not skills_lines and isinstance(skills, list):
            skills_lines.append(rf"\textbf{{Skills}}{{: {tex_escape(', '.join(skills))}}}")
        elif not skills_lines and isinstance(skills, dict):
            for k, v in skills.items():
                if isinstance(v, list):
                    skills_lines.append(rf"\textbf{{{tex_escape(k.replace('_', ' ').title())}}}{{: {tex_escape(', '.join(v))}}}")
                else:
                    skills_lines.append(rf"\textbf{{{tex_escape(k.replace('_', ' ').title())}}}{{: {tex_escape(str(v))}}}")
                    
        lines.append(" \\\\\n".join(skills_lines))
        lines.append(r"    }}")
        lines.append(r" \end{itemize}")
        lines.append("")

    lines.append(r"\end{document}")
    return "\n".join(lines)


def compile_resume(resume_json_path: Path, output_tex: Path) -> Path:
    if not resume_json_path.is_file():
        raise FileNotFoundError(f"Resume JSON file not found at {resume_json_path}")
        
    with open(resume_json_path, "r", encoding="utf-8") as f:
        resume_data = json.load(f)
        
    contact_info = resume_data.get("contact", {})
    latex_content = generate_latex_resume(resume_data, contact_info)
    
    output_tex.parent.mkdir(parents=True, exist_ok=True)
    with open(output_tex, "w", encoding="utf-8") as f:
        f.write(latex_content)
        
    print(f"Generating LaTeX source: {output_tex}")
    
    try:
        subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-output-directory=" + str(output_tex.parent), str(output_tex)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["latexmk", "-c", "-output-directory=" + str(output_tex.parent), str(output_tex)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        try:
            print("latexmk failed, falling back to pdflatex...")
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory=" + str(output_tex.parent), str(output_tex)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"Compilation warning: could not compile PDF (error: {e})")
            
    return output_tex.with_suffix(".pdf")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Compile resume JSON to LaTeX & PDF.")
    parser.add_argument("--resume", type=Path, default=Path("templates/experiences.json"), help="Path to resume.json")
    parser.add_argument("--output", type=Path, default=Path("resumes/Simon_Chen_Resume_Compiled.tex"), help="Output LaTeX path")
    
    args = parser.parse_args()
    
    pdf_path = compile_resume(args.resume, args.output)
    print(f"Compiled PDF successfully: {pdf_path}")
