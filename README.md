# worksisyphus

Simon Chen's resume compiler. One JSON database of everything I've done; Gemini picks what fits a job description, local code renders the LaTeX, and the result is always one page.

Gemini never writes resume text — it only selects IDs and names the output file. A hallucination can omit a bullet, never corrupt one.

## Layout

```text
├── compile.sh                  # rebuild the canonical full resume (no AI)
├── templates/experiences.json  # master database; values are TeX-formatted
├── src/worksisyphus/
│   ├── profile.py              # database loader + planner index
│   ├── planner.py              # Gemini JSON planner (selection + output name)
│   ├── selection.py            # Selection model + deterministic one-page trim order
│   ├── renderer.py             # Jake's-template TeX renderer (verbatim values)
│   ├── compiler.py             # pdflatex wrapper with page count
│   ├── pipeline.py             # tailor() and build_canonical()
│   ├── cli.py                  # worksisyphus compile | tailor
│   └── tui.py                  # paste-a-JD Textual dashboard
├── tex_files/                  # rendered TeX (only the canonical one is tracked)
└── resumes/                    # compiled PDFs (only the canonical one is tracked)
```

## Usage

Put your key in `.env`: `GEMINI_API_KEY=...`

```bash
# TUI: paste a JD, press Generate; output name is Gemini-chosen (e.g. bosch_swe_ii_resume.pdf)
uv run worksisyphus-tui

# CLI equivalents
uv run worksisyphus tailor --jd path/to/jd.txt     # or --jd - for stdin
uv run worksisyphus compile                        # canonical full resume, no AI
./compile.sh                                       # same as compile
```

Tailored output lands in `tex_files/<name>.tex` and `resumes/<name>.pdf`. If the first render runs past one page, the pipeline deterministically trims — lowest-ranked project first, then extra bullets — and recompiles until it fits; it fails loudly if it can't.

`templates/experiences.json` values are trusted TeX (`\$8K`, `75\%`, `$\sim$20$\mu$s`): escape special characters when editing.

## Tests

```bash
uv run python -m pytest tests/ -q
```
