# Simon Chen - Resumes & AI Compilation Tool

This repository contains the structured experiences database, LaTeX resume sources, and compiled PDF resumes/cover letters for Simon Chen. It includes an AI-powered tailoring tool that uses the Gemini API to customize your resume and cover letter for specific job descriptions.

## Directory Structure

```text
├── README.md                 # Project documentation
├── compile.sh                # Central compilation script for standard templates and JSON
├── .env                      # Local environment configurations (e.g. GEMINI_API_KEY)
├── src/                      # Source files
│   ├── compile.py            # Python compiler to generate resume from JSON
│   └── generate.py           # AI-powered resume & cover letter tailoring generator
├── templates/                # Folder containing templates and data
│   ├── experiences.json      # Centralized master experiences database in JSON
│   ├── resumes/              # LaTeX resume templates
│   │   ├── simon_chen_resume.tex # Primary software engineering resume
│   │   └── jakes_resume.tex  # Base professional resume
│   └── cover_letters/        # LaTeX cover letter templates
│       └── default.tex       # Generic default cover letter template
└── resumes/                  # Central output folder for compiled PDFs
```

## AI Custom Tailoring (Gemini)

You can generate a tailored resume and cover letter custom-built for any target Job Description (JD). 

### Prerequisites

Create a local `.env` file at the root and add your Gemini API Key:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### Usage

Run the tailoring script from the repository root:

```bash
# Generate both tailored resume and cover letter:
python src/generate.py --mode both --jd "Job Description text or path/to/jd.txt"

# Generate tailored resume only:
python src/generate.py --mode resume --jd "path/to/jd.txt"

# Generate tailored cover letter only:
python src/generate.py --mode cover-letter --jd "path/to/jd.txt"
```

The script will:
1. Read the master experiences list from `templates/experiences.json` and the target Job Description.
2. Call Gemini AI to select, order, and customize relevant skills, experiences, and projects to align with the JD, formatting it back as valid LaTeX.
3. Save the LaTeX files and compile them directly to `resumes/tailored_resume.pdf` and `resumes/tailored_cover_letter.pdf`.

---

## Standard Compilation

To compile all standard templates and the JSON resume directly without AI tailoring, simply run the compilation script:

```bash
./compile.sh
```

The script will:
1. Compile all LaTeX templates inside `templates/resumes/` and `templates/cover_letters/`.
2. Run `src/compile.py` to dynamically compile the structured `templates/experiences.json` data into LaTeX (`resumes/Simon_Chen_Resume_Compiled.tex`) and PDF (`resumes/Simon_Chen_Resume_Compiled.pdf`).
3. Clean up all intermediate build files, leaving only the compiled PDFs in the `resumes/` folder.

To compile only the standard JSON-based resume, run:

```bash
python src/compile.py --resume templates/experiences.json
```
