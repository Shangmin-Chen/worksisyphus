# Simon Chen - Resumes & Compilation Tool

This repository contains the structured JSON resume data, LaTeX resume sources, and compiled PDF resumes for Simon Chen.

## Directory Structure

```text
├── README.md                 # Project documentation
├── compile.sh                # Central compilation script for all templates and JSON
├── src/                      # Source files
│   └── compile.py            # Python compiler to generate resume from JSON
├── templates/                # Folder containing templates and data
│   ├── resume.json           # Centralized structured resume data in JSON format
│   ├── resumes/              # LaTeX resume templates
│   │   ├── simon_chen_resume.tex # Primary software engineering resume
│   │   ├── aclu_crm.tex      # Tailored ACLU CRM resume
│   │   └── jakes_resume.tex  # Base professional resume
│   └── cover_letters/        # LaTeX cover letter templates
│       ├── aclu_cover_letter.tex # Tailored cover letter for ACLU
│       └── default.tex       # Generic default cover letter template
└── resumes/                  # Central output folder for compiled PDFs
```

## Compilation

The repository uses `latexmk` from MacTeX. To compile all resumes and templates, simply run the compilation script from the repository root:

```bash
./compile.sh
```

The script will automatically:
1. Compile all LaTeX templates inside `templates/resumes/` and `templates/cover_letters/`.
2. Run `src/compile.py` to dynamically compile the structured `templates/resume.json` data into LaTeX (`resumes/Simon_Chen_Resume_Compiled.tex`) and PDF (`resumes/Simon_Chen_Resume_Compiled.pdf`).
3. Clean up all intermediate build files, leaving only the compiled PDFs in the `resumes/` folder.

To compile only the JSON-based resume, run the python compiler directly:

```bash
python src/compile.py --resume templates/resume.json
```
