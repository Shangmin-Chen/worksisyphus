# Simon Chen - Resumes & AI Compilation Tool

This repository contains the structured experiences database, deterministic LaTeX/PDF artifact pipeline, and compiled resume outputs for Simon Chen. The tailoring flow uses Gemini only to produce a structured JSON selection plan; final TeX is always built by the local deterministic renderer and compiled through the safe compiler backend.

## Directory Structure

```text
├── README.md                 # Project documentation
├── compile.sh                # Deterministic canonical resume rebuild wrapper
├── .env                      # Local environment configurations (e.g. GEMINI_API_KEY)
├── src/                      # Source files
│   ├── compile.py            # Deterministic JSON resume renderer/compiler wrapper
│   ├── generate.py           # Gemini JSON planner + deterministic artifact generator
│   └── worksisyphus/         # Canonical models, renderer, cache, and compiler backend
├── templates/                # Folder containing templates and data
│   ├── experiences.json      # Centralized master experiences database (values are TeX-formatted)
│   ├── resumes/              # LaTeX resume templates
│   │   └── jakes_resume_template.tex # Supported deterministic resume template
│   └── cover_letters/        # LaTeX cover letter templates
│       └── default_cover_letter.tex # Cover-letter template spec source
├── tex_files/                # Exported deterministic TeX artifacts
├── raw_inputs/               # Non-trusted raw imports, never compiled directly
└── resumes/                  # Central output folder for compiled PDFs
```

## Deterministic Tailoring (Gemini JSON Planner)

You can generate a tailored resume for a target Job Description (JD). Gemini receives the JD, the canonical profile index, and the template spec, then returns a JSON `SelectionPlan`. Gemini does not write final LaTeX. The local pipeline validates the plan, builds a render model, renders TeX from scratch, caches by artifact key, and compiles through the safe compiler backend.

### Prerequisites

Create a local `.env` file at the root and add your Gemini API Key:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### Usage

Run the tailoring script from the repository root:

```bash
# Generate tailored resume only:
python src/generate.py --mode resume --jd "path/to/jd.txt"

# Cover-letter rendering is currently fail-closed until its deterministic renderer lands:
python src/generate.py --mode cover-letter --jd "path/to/jd.txt"
```

The script will:
1. Read the master experiences list from `templates/experiences.json` and the target Job Description. Values in this file are trusted TeX (e.g. `\$8K`, `75\%`, `$\sim$20$\mu$s`) and are rendered verbatim — escape special characters when editing it.
2. Ask Gemini for a JSON-only selection plan containing canonical IDs.
3. Validate that plan against the canonical profile and selected `TemplateSpec`.
4. Render deterministic TeX locally and export it to `tex_files/<name>_resume.tex`.
5. Reuse a valid cached PDF when the artifact key already exists; otherwise compile trusted rendered TeX through `CompilerBackend`.

### Terminal User Interface (TUI) Dashboard

You can also launch an interactive, full-screen terminal dashboard:

```bash
uv run python src/tui.py
```

It is organized as four tabs, one per workflow:

- **Generate from JD** — paste a job description, pick templates, and run the deterministic planner/renderer/compiler path.
- **Import Raw TeX** — paste raw LaTeX as non-trusted input. Imports are saved under `raw_inputs/tex_imports/*.raw.txt` and are not compileable artifacts.
- **Compile** — rebuild the canonical JSON resume through `src/compile.py`; it does not compile selected arbitrary `.tex` files.
- **Database** — read-only browser for `templates/experiences.json`.

Key bindings: **Ctrl+L** clears the activity log, **Ctrl+Q** quits.

The supported resume template spec is `jakes_resume`, backed by `templates/resumes/jakes_resume_template.tex`. Exported `.tex` files in `tex_files/` are deterministic artifacts; raw imports live outside that trusted artifact path.

---

## Standard Deterministic Compilation

To rebuild the canonical JSON resume without AI tailoring, run:

```bash
./compile.sh
```

The script will:
1. Run `src/compile.py` against `templates/experiences.json`.
2. Render deterministic TeX to `tex_files/Simon_Chen_Resume_Compiled.tex`.
3. Reuse a valid cached PDF for the same profile/template/compiler artifact key when available.
4. Otherwise compile trusted rendered TeX and export `resumes/Simon_Chen_Resume_Compiled.pdf`.

It intentionally does not glob over `tex_files/*.tex` and does not compile user-provided TeX.

To compile only the standard JSON-based resume, run:

```bash
python src/compile.py --resume templates/experiences.json
```

For a custom TeX output path, the PDF defaults next to it:

```bash
python src/compile.py --resume templates/experiences.json --output /tmp/resume.tex
# PDF output defaults to /tmp/resume.pdf
```

## Benchmark

Run the production-readiness benchmark:

```bash
PYTHONDONTWRITEBYTECODE=1 python src/benchmark.py
```

The benchmark grades tests, determinism/cache reuse, safety/atomicity, compile
status, and TUI/tooling readiness. See [docs/benchmark.md](docs/benchmark.md)
for the scoring rubric and current residual risks.
