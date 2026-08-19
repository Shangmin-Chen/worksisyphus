# worksisyphus

Simon Chen's resume compiler. One slug-keyed JSON database of everything I've done; a plan file picks what fits a job description, local code renders the LaTeX, and the result is always one page.

Nothing writes resume text but me. A plan can omit a bullet, never corrupt one — whether the plan is written by hand or by an AI agent.

## Prerequisites

- **Python package manager**: `uv` (`brew install uv`)
- **LaTeX distribution**: **MacTeX** is required for `pdflatex` to compile rendered LaTeX resumes into PDFs.
  - Install via Homebrew:
    ```bash
    brew install --cask mactex      # Full MacTeX distribution
    # or
    brew install --cask basictex    # Lightweight distribution
    ```
  - Ensure `/Library/TeX/texbin` is in your PATH (e.g. `eval "$(/usr/libexec/path_helper)"`). The compiler automatically checks standard MacTeX paths and raises an explicit error if missing.

The intended workflow is agent-driven. `CLAUDE.md` teaches Claude Code the rules (one page, Jake's template, select-don't-write, content guardrails), so tailoring a resume is one prompt:

1. Open Claude Code in this repo: `claude`
2. Paste the job description:
   > Tailor my resume to this JD: *(paste the whole posting, company name included)*
3. Claude runs the pipeline: reads the slug index, writes `plans/<company>_<role>.json` ranked by relevance, validates it, compiles the one-page PDF, and runs the ATS extraction check.
4. The resume is done when it's exactly one page and the ATS check passes — no sign-off loop. Claude delivers the PDF with what it picked, why, and anything the trim loop cut. (Content edits are different: Claude may propose bullet rewordings but never touches `profile.json` without my approval.)
5. `resumes/Simon_Chen_Resume.pdf` is what goes to the employer — every tailored resume gets that same recruiter-friendly filename. The 3-page canonical never goes out.
6. Claude then freezes the application with `worksisyphus archive` into `applications/<date>_<name>/` — the JD verbatim, the frozen plan, the exact PDF sent, and a `meta.json` with a `status` field. That folder is the immutable record for callbacks ("which applications are still open?" is answered from `applications/*/meta.json`).

List tracked applications with `worksisyphus status`. Update one with
`worksisyphus update-status --app <folder-or-unique-plan-stem> --status <status>`.

Useful follow-up prompts: "swap hermes-letters for the home server", "make it lean more infra than frontend", "show me what the trim loop would cut first".

## Manual usage (no agent)

```bash
uv run worksisyphus index                         # list every slug a plan can reference
uv run worksisyphus validate --plan plans/x.json  # check a plan and print the resolved selection
uv run worksisyphus tailor --plan plans/x.json    # one-page resume from a plan (- for stdin)
uv run worksisyphus archive --plan plans/x.json --company Acme --jd <file|->   # freeze an application folder (- for stdin)
uv run worksisyphus status                        # list archived applications and identifiers
uv run worksisyphus update-status --app <folder-or-unique-plan-stem> --status phone_screen
uv run worksisyphus db status                        # show database stats and metrics
uv run worksisyphus db history [--limit N]           # show timestamped append-only audit trail
uv run worksisyphus db sync                          # export profile.json and sync to Turso cloud
uv run worksisyphus compile                       # canonical full resume (./compile.sh is the same)
uv run --with pdfminer.six python scripts/ats_check.py resumes/x.pdf   # ATS extraction check
```

Every tailored resume compiles to `resumes/Simon_Chen_Resume.pdf` — a clean, human filename for recruiters; per-application copies are frozen under `applications/`. If the first render runs past one page, the pipeline deterministically trims — lowest-ranked project first, then extra bullets — and recompiles until it fits; it fails loudly if it can't.

## Layout

```text
├── compile.sh              # rebuild the canonical full resume
├── profile.json            # master database; slug-keyed, values are TeX-formatted
├── plans/                  # plan files (see plans/example.json)
├── applications/           # one immutable folder per application: jd, plan, pdf, meta
├── CLAUDE.md               # rules for AI agents operating this repo
├── scripts/ats_check.py    # verify a compiled PDF extracts cleanly for ATS parsers
├── src/worksisyphus/
│   ├── db.py               # SQLite/Turso database & append-only audit trail
│   ├── profile.py          # database loader + slug index
│   ├── plan.py             # plan-file parser and validation
│   ├── selection.py        # Selection model + deterministic one-page trim order
│   ├── renderer.py         # Jake's-template TeX renderer (verbatim values)
│   ├── compiler.py         # pdflatex wrapper with page count
│   ├── pipeline.py         # tailor() and build_canonical()
│   ├── archive.py          # freeze sent applications into applications/
│   └── cli.py              # compile, tailor, validate, archive, and track applications
├── tex_files/              # rendered TeX (only the canonical one is tracked)
└── resumes/                # compiled PDFs (all tracked)
```

## Plan files

A plan is a small JSON file of slugs; order is rank (most relevant first), which also drives the trim order:

```json
{
  "experiences": {
    "reset-standard": "all",
    "ezesports": ["nextjs-migration", "supabase-schema"]
  },
  "projects": ["persephone", "hermes-letters"],
  "skills": "all"
}
```

- `experiences`/`projects`: an object of `slug -> "all" | [bullet slugs]`, or a plain list of slugs (each meaning all bullets).
- `skills`: `"all"` (the default when omitted), or an object of `group -> "all" | [items copied verbatim]`.
- The plan's filename identifies the application; the output PDF is always `Simon_Chen_Resume.pdf`. Unknown slugs fail loudly.

`profile.json` values are trusted TeX (`\$8K`, `75\%`, `$\sim$20$\mu$s`): escape special characters when editing.

## Tests

```bash
uv run python -m pytest tests/ -q
```
