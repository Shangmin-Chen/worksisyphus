# Job Hunt Resume Repository

This repository contains the structured JSON resume data, LaTeX resume sources, and compiled PDF resumes for Simon Chen.

## Directory Structure

```text
job-hunt/
├── README.md                 # Project documentation
├── resume.json               # Centralized, structured resume data in JSON format
├── compile.sh                # Compilation script for compiling .tex files to resumes/
├── src/                      # LaTeX source files (.tex)
│   ├── Simon_Chen_Resume.tex # Primary software engineering resume source
│   ├── aclu_CRM.tex          # Tailored resume source for ACLU CRM role
│   └── jakes_resume_template.tex # Standard template base
└── resumes/                  # Compiled output PDFs
    ├── Simon_Chen_Resume.pdf # Primary compiled resume
    └── aclu_CRM.pdf          # Tailored compiled resume for ACLU CRM role
```

## Compilation

The repository uses `latexmk` from MacTeX. To compile all resumes in `src/` and output them to `resumes/`, run the compilation script from the repository root:

```bash
./compile.sh
```

The script will automatically compile all `.tex` files, move the output PDFs to `resumes/`, and clean up intermediate auxiliary build files.

## Resume Variants

* **Simon_Chen_Resume.pdf**: The primary, comprehensive resume targeting Software Engineering, Full-Stack development, and quantitative systems/infrastructure roles.
* **aclu_CRM.pdf**: A customized, single-page resume tailored specifically for the ACLU CRM Software Engineer role, highlighting ServiceNow workflows, client registry projects, database schemas, and data pipelines.
