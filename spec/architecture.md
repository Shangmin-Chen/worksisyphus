# Architecture evolution

Do not resurrect dead layouts. File counts are `git ls-tree -r --name-only` at that commit.

## Current module map at `b654120`

Render path (left to right). **`profile.json` → `pipeline` never reads SQLite/Turso** for bullets or TeX:

`profile.json` → `profile.py` (slug-keyed loader; `validate_contact` used by callers, not inside `load_profile`) → `plan.py` (parse/validate slugs) → `selection.py` (Selection + deterministic trim order) → `renderer.py` (Jake's-template TeX; values verbatim; copies preamble from `source_of_truth_resume.tex`) → `compiler.py` (`pdflatex` + page count; PATH and `/Library/TeX/texbin`) → `pipeline.py` (`tailor()` preview into `tex_files/`, `build_canonical()`) → `application.py` (1-step `apply`, lifecycle, evaluations, folder allocator) → `cli.py`.

Off to the side — **store, not source of bullets/TeX:**

- `db.py` — SQLite `worksisyphus.db`, Turso push, append-only audit, seed/export, application rows. Types imported from `profile.py`. Seeded from `profile.json`; receives application records from `application.py`. **`apply` also reads the contact row** via `cross_check_contact_against_db` (`371cbe5`) before publish — mismatch blocks delivery; missing DB skips the check.
- `git_guard.py` — branch + `origin/main` freshness for any Turso push (`apply`, `update-status`, `backfill-evals`, `db sync`/`init`).

Quality and scoring, invoked by `apply` / CLI, not by the renderer:

- `ats.py` (from `scripts/ats_check.py`, which still exists)
- `gates.py` (No-GPA, banned content, LaTeX leaks, density)
- `optimizer.py` (knapsack + `apply_selection_guardrails`)
- `evaluator.py` + `hiring_agent.py` + `roles/` (HackerRank-shaped rubrics)

`cli.py` lazy-imports db/optimizer/evaluator/hiring_agent per subcommand.

Tracked at HEAD (**73** files; no `profile.json`, no `applications/`): `source_of_truth_resume.tex`, `compile.sh`, `tex_files/Simon_Chen_Resume_Compiled.tex` (gitignore exception; only tracked TeX), `CLAUDE.md`, `GEMINI.md`, `README.md`, `.env.example` (Turso placeholders; `.env` gitignored since `bf242bf`), `.python-version`, `scripts/ats_check.py`, `tests/` (including `tests/fixtures/profile.json` — test-only, scrubbed contact), `.github/workflows/ci.yml`. `src/worksisyphus/roles/upstream_manifest.json` holds the tracked ETag/upstream SHA for `--check-upstream` (not `.provenance.json`, which died with `resumes/`).

`src/worksisyphus/`: 15 feature modules + `__init__.py` / `__main__.py` + `roles/` (8 role dirs: `ai_engineer`, `mle`, `product_engineer`, `quant_engineer`, `software_engineer`, `software_engineering_intern`, `startup_product_engineer`, `systems_engineer`).

`profile.json` and `applications/` are gitignored (`8e89415` / `dfa1022` anchors). `worksisyphus.db` is gitignored. `.gitignore` `/plans/` is a tombstone (`c3e22a0`).

### Apply data flow at HEAD

`apply --company --jd [-] [--plan]` loads `profile.json` via `load_profile` (missing file is fatal), validates contact, then **`cross_check_contact_against_db`** reads the contact row when `worksisyphus.db` exists — mismatch blocks; **no DB file skips the check** (fail-open). If `--plan` is omitted, `optimizer.py` searches and runs `apply_selection_guardrails`. `plan.py` resolves slugs; `selection.py` ranks for the trim loop. `renderer.py` calls `validate_contact` (non-empty fields) and copies the Jake preamble. `compiler.py` runs `pdflatex` in a private temp tex dir (`e4f4cd2`). `gates.py` + `ats.py` must pass; overflow fails only when overfull **> 2pt**. `application.py` allocates `applications/<YYYY-MM-DD>_<stem>[_N]/`, writes `jd.txt`, `plan.json`, `Simon_Chen_Resume.pdf`, `meta.json` (status, evaluation, **`contact_verification` always** — `ran` / `skip_reason`, not only when the check ran), then inserts into SQLite **only if the DB file exists**, then `git_guard.py` decides whether Turso may be pushed. **No `worksisyphus.db` → folder still publishes, no SQLite row, no Turso, exit 0.** Turso skip reasons (git gate, missing CLI, dump/CLI errors) warn and return; none fail `apply`. Unmerged `fix/46-db-silent-data-loss` would tighten this.

```
cli.apply  (or pipeline.tailor preview / pipeline.build_canonical)
  → profile.load_profile          # missing file is fatal
  → validate_contact + cross_check_contact_against_db   # before pdflatex; mismatch blocks
  → plan.parse_plan               # or optimizer.optimize_plan if apply omits --plan
  → selection (full_selection / trim_step)
  → renderer.render_resume        # validate_contact (non-empty); SoT preamble
  → compiler.compile_tex
  → gates.run_resume_gates → ats.check_pdf_ats
  → application.apply writes applications/<YYYY-MM-DD>_<stem>/  (os.replace)
  → db insert + git_guard → optional Turso   # skipped when no DB file; Turso errors warn only
```

`meta.json` at HEAD: `company`, `role`, `date`, `source_url`, `status`, `evaluation` (from `f2165f3`), `contact_verification` (from `371cbe5`; absent on older folders). Only `status` and backfilled `evaluation` are allowed to change after publish.

## Directory snapshots

### `d78f844` — LaTeX shop root (2025-09-19) — 4 files

```
./
├── master_resume.tex          # 213 lines
├── tailored_resume.tex
├── ai_agent_prompt.txt        # empty; content arrives b2224a7
└── job_description.txt
```

### `191194d` — after subtree merge (2026-07-02) — 50 files

```
./
├── README.md, pyproject.toml, uv.lock
├── job hunt/                  # entire 0af3a16 tree
│   ├── compile.sh, resume.json
│   ├── src/*.tex              # Simon_Chen, aclu_*, jakes_*
│   ├── resumes/*.pdf
│   └── .agents/AGENTS.md
└── src/worksisyphus/{aggregator,catalog,enricher,normalizer}/
```

### `e57ff6a` — deterministic rewrite (2026-07-08) — 46 files

```
./
├── compile.sh, docs/, templates/, tex_files/, resumes/
├── src/{compile,generate,tui,benchmark}.py
└── src/worksisyphus/{compiler,planner,profile,renderer,selection,artifacts,benchmark,models,templates}.py
```

### `06e3587` — slug pipeline (2026-07-11) — 30 files

```
./
├── profile.json, plans/example.json, CLAUDE.md, scripts/ats_check.py
├── resumes/, tex_files/
└── src/worksisyphus/{cli,pipeline,plan,profile,renderer,selection,compiler}.py
```

TUI gone; `planner.py` → `plan.py`; `templates/` gone.

### `3df5a44` — unified apply (2026-08-20) — 120 files

```
./
├── profile.example.json, plans/, source_of_truth_resume.tex
├── resumes/, applications/    # still tracked
└── src/worksisyphus/{application,archive,ats,db,evaluator,gates,hiring_agent,optimizer,...}.py
```

`archive.py` + `application.py` coexist briefly (~5 min until `a84b998`).

### `c3e22a0` — after `resumes/` + `plans/` deleted (2026-08-23) — 71 files

```
./
├── source_of_truth_resume.tex, compile.sh, CLAUDE.md, GEMINI.md, README.md
├── tex_files/Simon_Chen_Resume_Compiled.tex
└── .gitignore → /applications/, /profile.json, /plans/
```

`archive.py` already gone (`a84b998`). Delivered PDFs/plans live only locally + Turso.

### `b654120` — HEAD (2026-09-13) — 73 tracked files

```
./
├── source_of_truth_resume.tex, compile.sh
├── CLAUDE.md, GEMINI.md, README.md, pyproject.toml, uv.lock
├── .env.example, .python-version, .gitignore
├── .github/workflows/ci.yml
├── scripts/ats_check.py
├── tex_files/Simon_Chen_Resume_Compiled.tex
├── src/worksisyphus/          # 15 feature modules + __init__/__main__ + roles/
└── tests/                     # conftest.py, fixtures/profile.json, 16 test_*.py
```

**Not in git at HEAD:** `profile.json`, `applications/`, `plans/`, `resumes/`. README's layout still draws `profile.json` and **deleted** `profile.example.json` — see `docs-drift.md`.

## How it got here

### LaTeX shop (second parent: `d78f844` → `0af3a16`)

Single `master_resume.tex` / `tailored_resume.tex` pair, then `resumes_latex/` role variants + PDFs under `resumes/`. `0af3a16` introduces structured `resume.json`, `src/*.tex`, `compile.sh`, ACLU templates, Jake's template, `.agents/AGENTS.md`.

### Two-root merge then flatten (`56767dc` → `6ed0848`)

Python aggregator package under `src/worksisyphus/{aggregator,normalizer,enricher,catalog}`. `191194d` drops the LaTeX shop in as `job hunt/`. `6ed0848` **deletes the aggregator** and flattens `job hunt/` into `templates/` + `resumes/` + `src/compile.py`.

### Gemini / TUI week (`018f680` → `f3ca492`)

`experiences.json` + `src/generate.py` (Gemini generation) + Textual `src/tui.py` / later `src/worksisyphus/tui.py`. `e57ff6a` creates the package (`planner.py`, `benchmark.py`, docs). `f3ca492` keeps Gemini selection + TUI, kills generate/benchmark/cache, adds the trim loop.

### Slug pipeline (`06e3587` → `11fe095`)

`profile.json` + `plan.py` + `plans/*.json` + `archive.py` + `applications/` + `CLAUDE.md`. TUI and Gemini planner gone. `643da17` adds `source_of_truth_resume.tex`. Shared tailor output still `resumes/Simon_Chen_Resume.pdf`.

### Productization (`509d522` → `11a6ac2`)

`db.py`, `ats.py`, `gates.py`, `optimizer.py`, `evaluator.py`, `hiring_agent.py`, `roles/`, `.github/workflows/ci.yml`, `application.py`. `archive.py` deleted (`a84b998`). `resumes/` deleted (`edeb27c`). `plans/` deleted (`c3e22a0`). `profile.example.json` existed `8e89415`–`6640a8b` only. `db sync` flipped from export-to-disk (`99deed6`) to seed-from-profile (`6640a8b`).

### Hardening (`e4f4cd2` → `b654120`)

`git_guard.py` born `39fad80`. `profile.py` fail-closed missing file + `validate_contact`. `application.py` slot allocator + `contact_verification`. `optimizer.py` `OptimizerError`. `db.py` seed/export guards + sync gate.

## Path registry (do not resurrect)

| Path | Born | Died | Replaced by | LLM trap |
|------|------|------|-------------|----------|
| `master_resume.tex` | `d78f844` | `17b1e90` (renamed → ML variant; new `resumes_latex/master_resume.tex`) | `resumes_latex/` → `src/Simon_Chen_Resume.tex` → `source_of_truth_resume.tex` | Root-level `.tex` master; `git log --follow` lands in ML variant |
| `tailored_resume.tex` | `d78f844` | `17b1e90` (renamed → `new_grad_software_engineer_resume.tex`) | renderer output / `tex_files/` | Single tailored TeX at repo root |
| `ai_agent_prompt.txt` | `d78f844` (empty); text `b2224a7` | `17b1e90` | `CLAUDE.md` (`06e3587`), `GEMINI.md` (`64c0830`) | Prompt `.txt` driving tailoring |
| `job_description.txt` | `d78f844` | `17b1e90` | `applications/*/jd.txt`; `--jd -` | Sample JD at root |
| `resumes_latex/` | `17b1e90` (consolidated `de15db6`) | `0af3a16` | `src/*.tex` | Multi-resume LaTeX folder |
| `job hunt/` | `191194d` | flattened `6ed0848` | hoisted to repo root | Prefixing `job hunt/` |
| `compile.sh` | `0af3a16` | — live | wraps `uv run python -m worksisyphus compile` | Assuming pdflatex is Python-only |
| `src/*.tex` (aclu_*, jakes_*, Simon_Chen) | `0af3a16` | `c8b2e27`–`06e3587` | SoT + in-memory body | Hand-editing per-role TeX |
| `src/worksisyphus/aggregator/` (+ catalog, enricher, normalizer) | `56767dc` | `6ed0848` | unrelated; gone | Job-ingest CLI under this package |
| `templates/` (`resume.json` → `experiences.json`) | `6ed0848` / `018f680` | `06e3587` | `profile.json` + SoT | `experiences.json` as SSoT |
| `templates/cover_letters/`, ACLU tex | `0af3a16` / `6ed0848` | ACLU `c8b2e27`; junior_ai_cv `8c83568` | — | Civic/CRM template path (none after this) |
| `src/{compile,generate,benchmark}.py` | `6ed0848` / `e57ff6a` | `f3ca492` | `cli.py` | Top-level scripts |
| `src/tui.py` / package TUI | `c8b2e27` / `f3ca492` | `f3ca492` / `06e3587` | CLI + `apply` | Textual dashboard |
| `planner.py`, `benchmark.py`, `artifacts.py` | `e57ff6a` | `f3ca492` / `06e3587` | `plan.py` + `selection.py` | “Planner” module |
| `docs/deterministic-compiler-plan.md` | `e57ff6a` | `2892302` / `f3ca492` | README/CLAUDE | `docs/` plan |
| `archive.py` | `ba62443` | `a84b998` | `application.py` | `worksisyphus archive` |
| `profile.json` | `06e3587` | tracked until `8e89415` | gitignored local SSoT; `db sync` seeds SQLite | Committing it or expecting it in CI |
| `profile.example.json` | `8e89415` | `6640a8b` | `tests/fixtures/profile.json` (`dfa1022`) | Template at repo root (README still lists it) |
| `plans/`, `plans/example.json` | `06e3587` | `c3e22a0` | scratch + `applications/*/plan.json` | Recreating tracked `plans/` (gitignore `/plans/`) |
| `plans/drafts/` | `f553ff6` | `c3e22a0` | — | Draft-plans folder |
| `resumes/` (shared tailor PDF, `.provenance.json`, `.tailor.lock`) | LaTeX shop / `f3ca492` | `edeb27c` | `applications/<date>_<stem>/Simon_Chen_Resume.pdf` | `resumes/<company>_resume.pdf` |
| `applications/` | `ba62443` | — live, gitignored `8e89415`/`dfa1022` | sole delivery home | Expecting app history in git |
| `source_of_truth_resume.tex` | `643da17` | — live | preamble source | Editing preamble to squeeze content |
| `tests/fixtures/profile.json` | `dfa1022` | — live | CI/tests only | Using as production profile (`e74bcee`) |
| `.agents/AGENTS.md` | `0af3a16` | dropped with flatten / CLAUDE.md | `CLAUDE.md` | Root `AGENTS.md` |
| `tex_files/` | `8c83568` | — partial | build scratch; only compiled canonical `.tex` tracked | Treating tailor output as delivered; `e57ff6a` adds files under an existing dir |
| `worksisyphus.db` | `99deed6` | gitignored | Turso | Treating DB as render input |

### Module births (`src/worksisyphus/*.py`)

| Module | Born | Died |
|--------|------|------|
| `profile`, `selection`, `renderer`, `compiler` | `e57ff6a` (slug schema `06e3587`) | — |
| `artifacts`, `benchmark`, `models`, `templates`, `planner` | `e57ff6a` | `f3ca492` / `06e3587` |
| `pipeline`, `cli` | `f3ca492` | — |
| `archive` | `ba62443` | `a84b998` |
| `application` | `3df5a44` | — |
| `db` | `99deed6` | — (store; `apply` reads contact row only) |
| `ats` | `c0abbcc` | — |
| `gates` | `8c75336` | — |
| `hiring_agent`, `evaluator` | `1a32d53` | — |
| `optimizer` | `97068bc` | — |
| `git_guard` | `39fad80` | — |

## Tests and CI

`tests/` exist from `e57ff6a` onward; they must pass without network or `pdflatex` (fake compiler, in-memory SQLite, fixture profile). After `8e89415`, PDF-backed ATS/gate/evaluator tests skip in CI (`edeb27c` documents this). `tests/test_consistency.py` began as plan↔archive (`1e0c6f4`), then applications+DB (`35ad6d8`), then dropped plan-matching tests (`c3e22a0`). **16** `test_*.py` at HEAD, not 18 (plus `conftest.py` + `fixtures/`).

After `edeb27c` / `4320d04`, CI does not ATS-check a tracked employer PDF (there is none). Gate tests use fakes/fixtures; pdflatex is local. CI also runs `ruff format --check`. Agents must not assume GitHub Actions proved a one-page employer PDF.

## LLM traps (paths)

1. **`plans/`** — deleted `c3e22a0`. Scratch JSON outside the repo; `apply` freezes it. Gitignore `/plans/`.
2. **`resumes/`** — deleted `edeb27c`. Only `applications/<date>_<stem>/Simon_Chen_Resume.pdf`.
3. **TUI / `generate.py` / `archive` / `job hunt/` / `templates/` / `profile.example.json`** — all dead.
4. **Fixture fallback** — gone from production `load_profile`/`seed_database` (`e74bcee`/`652ff4f`). **`tests/conftest.py` `real_profile` still falls back to the fixture for CI** — do not port that into `profile.py`. Never load the fixture for delivery.
5. **Editing Jake preamble / margins**, or treating `tex_files/` tailor output as delivered — preview only; fit by selecting less.
6. **Root `jd.txt`** — agents were told `--jd -` (`310a65e`) so they do not drop JD files in the repo root.
7. **Rendering from Turso/SQLite** — forbidden. Recovery is one-way at a time: lost `profile.json` → `db export-profile`; good profile / stale DB → `db sync`. Atomic export (`fix/50-atomic-export-profile`) is unmerged — HEAD write is a direct `Path.write_text`.
