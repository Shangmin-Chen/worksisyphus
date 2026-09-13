# Invariants (as of `b654120`)

Landing hash = the commit that introduced the behavior on ancestry that reached HEAD, not
necessarily the GitHub merge. **Code** = argparse, tests, or a pipeline raise. **CLAUDE.md** =
agent judgment. The optimizer encodes a subset of the selection gates **only when `--plan` is
omitted**. “Weakened” means a later HEAD commit narrowed or reversed it.

## Live

| Invariant | Landed | Enforcement | Notes |
|-----------|--------|-------------|-------|
| One-page tailored PDF + trim loop | `f3ca492` | Code `pipeline.PAGE_LIMIT`, `selection.trim_step`, compiler page count | Apply fails if it cannot fit. Never bypass by shrinking Jake's template. CLAUDE.md restates. Horizontal overflow fails only when overfull **> 2.0pt** (`OVERFULL_TOLERANCE_PT`, `643da17`); smaller overfulls can still exit 0. |
| Jake's template / preamble untouched | Prose `0af3a16`; code `643da17` | Both | `source_of_truth_resume.tex` copied verbatim in memory; body replaced. Do not change fonts, margins, or section spacing. |
| Select, propose, never write | Prose `b2224a7`; slugs `06e3587` | CLAUDE.md | Agent picks slugs; `plan.py` cannot invent bullet text. Propose new wording to the user; never edit `profile.json` without approval of that text. A plan may omit a bullet, never corrupt one. |
| TeX values rendered verbatim | `0146d92` | Code `renderer.py` | Escape `$`, `%`, `&`, `#` in `profile.json` (`\$8K`, `75\%`). Math like `$\sim$20$\mu$s` is intentional. |
| Employer filename `Simon_Chen_Resume.pdf` | `da54f09` | Code `selection` / `application.py` | Not a CLI flag. Folder stem carries company/role. **Reversal of** Gemini-named outputs (`f3ca492`). Display name **Simon Chen** since `a0e025d` (was Shangmin Chen in pre-Dec-2025 tex); GitHub/LinkedIn slugs stay `shangmin-chen`. |
| Never send the canonical 3-page | `06e3587` | CLAUDE.md only | `compile` / `compile.sh` still build `Simon_Chen_Resume_Compiled.pdf` as Simon’s database view. **~3 pages is content length at HEAD, not enforced** — `build_canonical` has no page limit; overflow there is a warning only. Nothing in the pipeline can stop someone from attaching that file. |
| `applications/` is the only delivered-resume home | `edeb27c` (merge `2a57152`) | Code | No `resumes/` mirror. |
| `tailor` never delivers | `f553ff6` | Code | Writes `PREVIEW_DIR` (`tex_files/`); stdout reminder to `apply`. Never send that PDF. |
| Plans are inputs, not artifacts | `c3e22a0` (merge `11a6ac2`) | Code + `.gitignore` `/plans/` | Scratch `$TMPDIR/<company>_<role>.json`. `apply` freezes `applications/.../plan.json` and Turso `plan_json`. |
| `apply` is the 1-step delivery path | `3df5a44` (merge `6564917`); `archive` deleted `a84b998` | Code | Contact cross-check **before** compile. Compile → quality gates → ATS → folder freeze → DB insert (only if `worksisyphus.db` exists) → Turso (if git gate allows; skips warn, never fail apply). **No DB file → folder publishes, no SQLite/Turso, exit 0.** Deliver when `apply` exits 0; no sign-off (`ba62443` dropped it). |
| `--jd` required; empty JD refused | Archive `1e0c6f4`; apply inherited | Code | argparse `required=True` plus `application.py` `ValueError` if blank. Prefer `--jd -`. If there is no posting, pipe an explanatory note. **Single-stdin is prose-only** (`docs-drift.md`). |
| Application folders immutable after publish | `ba62443` / apply `3df5a44`; allocator `e4f4cd2` | Code | Only `meta.json.status` (and `evaluation` via `backfill-evals`) may change. Same-day retry allocates a new folder rather than overwrite. **One-time exception:** `11fe095` regenerated every archived PDF from frozen `plan.json` at explicit user request — do not repeat; HEAD code still refuses to mutate published folders. |
| Same-day `_N` suffixes | `e4f4cd2` (merge `5bf891e`) | Code `_allocate_target` | Lowest free `_2`, `_3`, …; `os.replace` + ENOTEMPTY retry. Status App#. Before this, same-day re-apply was `FileExistsError`. |
| No GPA | Removed `6b52555`; gate `8c75336` | Both | GPA **added** `2c8149a` (3.53), still 3.58 in `06e3587`, **removed** `6b52555`. The *presence* of GPA was reversed; the *ban* was not. If a form demands GPA, flag Simon; do not add it to the resume. |
| Persephone-first | `06e3587` CLAUDE.md; optimizer `6640a8b` | Both* | Backend / systems / infra / performance / quant. **Hand `--plan` bypasses optimizer.** |
| Weak-project gate | `06e3587`; optimizer `6640a8b` | Both* | `fitness-tracker`, `spark-food-waste`, `ml-marketplace` only when the JD *is* mobile / civic-impact / blockchain. |
| Personal-website gate | `5175332`; optimizer `6640a8b` | Both* | Frontend / full-stack / web-infra / edge only. A portfolio site weakens a resume where `persephone` and `hermes-letters` already carry the engineering signal. |
| BU IT gate | `06e3587`; optimizer `6640a8b` | Both* | `bu-engineering-it` only for IT / support / security-adjacent JDs, never pure SWE. |
| Banned piracy-adjacent names + fake metrics | Content `f010d71`; CLAUDE.md `06e3587`; gate `8c75336` | Both | `gates.BANNED_TOOLS`: Sonarr / Radarr / Prowlarr / Jellyfin / qBittorrent / Slskd / Soulseek. Also `BANNED_METRIC_PATTERNS` (“uptime by 15%”, “100% incident resolution”). Keyword-stuffed skills = CLAUDE.md only. |
| Five quality gates block delivery | `8c75336`, wired `c42e91a` / `6564917` | Code | ATS extraction (+ page count inside ATS gate), No-GPA, Banned Content, LaTeX Leaks, Content Density (tailored ≥350 words / 1500 chars; canonical ≥900 / 4000). Page count and horizontal overflow (>2pt) are pipeline checks, not separate named gates. All must pass for `apply` to publish. |
| `db.py` is a store, not a source | `99deed6` | Both | Render path reads `profile.json` only. DB is seeded by `db sync` and fed application rows by `apply` when the file exists. **`apply` reads the contact row for cross-check before pdflatex** (`371cbe5`); mismatch on any of six fields (`name`, `email`, `phone`, `website`, `github`, `linkedin`) blocks. Missing DB file skips cross-check, insert, and Turso — folder still publishes. Empty DB contact row skips (not mismatch). |
| `profile.json` and `applications/` gitignored; Turso is the cloud mirror | `8e89415` / `dfa1022` | Code `.gitignore` | `profile.example.json` added `8e89415` and **deleted** `6640a8b`. Fresh clones do not contain application PDFs. |
| Every apply records a HackerRank evaluation | `f2165f3` | Code | `meta.json["evaluation"]`, DB `evaluation_json`. `backfill-evals` covers folders that predate this. |
| Missing `profile.json` is a hard error | Fallback `85c6d1b` / `dfa1022`; **closed** `e74bcee` / `652ff4f` | Code `load_profile` | `FileNotFoundError` naming `db export-profile`. `tests/fixtures/profile.json` still exists for tests; delivery must never load it. |
| Contact required fields non-empty | `e00b1e3`; **simplified `afb3dc7`** | Code `validate_contact` | See **HEAD mismatch**. `load_profile` itself does **not** call it. |
| Seed must not invent a profile | `652ff4f`, `dab87a5` | Code | Seed via `load_profile` then `validate_contact` (non-empty) before `init_schema`. Failed seed on a fresh DB leaves no tables. File existence is not content validation. |
| Export recovery constraints | CLI `e74bcee`; validate-on-write `652ff4f` | Code `export_profile_json` | `--force` only clobbers an existing destination; it is not a licence to skip `validate_contact`. At HEAD that check is non-empty fields, not placeholder strings. |
| Delivery contact cross-check + `contact_verification` | `371cbe5`; DB-side `dab87a5` | Code | Six-field mismatch blocks; skip (no DB / no contact row) still writes `contact_verification` with `skip_reason`. Folders published before ~2026-08-31 omit the field (“not recorded,” not verified). Blocklist weakened `afb3dc7`. LinkedIn `www.` archaeology (`da81003`) can fail apply if profile and DB disagree. |
| Optimizer never returns an unscored plan | `9923c95` | Code | `OptimizerError`; guardrails on the degenerate `<2 projects` branch. CLI exit 1. |
| Turso sync git freshness | `39fad80`; fail-closed `e92de45` (merge `b654120`) | Code `git_guard.py` | `main` (or `--allow-branch` on a **named** non-main branch), not behind `origin/main`, upstream verifiable. Detached HEAD cannot sync. Escape: `--no-sync`, `--allow-branch`, `--no-git-check`. |
| Unified application identifier (FS + DB) | `e4f4cd2` | Code `match_application_identifier` | No SQL `LIKE` wildcards. Ambiguity lists every matching folder. |
| MacTeX / pdflatex discovery | `c76e53a` | Code `compiler.py` | PATH and `/Library/TeX/texbin`. Missing `pdflatex` fails with `brew install --cask mactex`. |
| Exit 0 / 1 + `error: …` on stderr | `f3ca492`+ | Code `cli.main` | Plan validation errors name the offending slug. |
| `compile.sh` thin wrapper | `0af3a16` / `f3ca492` | Tracked script | `exec uv run python -m worksisyphus compile`. Live, not the only compile path. |
| Deterministic enforcement over prose | `1e0c6f4` | CLAUDE.md (meta) | Exemplar: `--jd required=True`. Single-stdin and placeholder-export wording are counterexamples still in prose. |

\* Optimizer `apply_selection_guardrails()` mirrors persephone-first / weak-project / personal-website / BU IT **only for generated plans**. `validate --plan` / `apply --plan` do **not** run those filters.

## HEAD mismatch: placeholder contact

At **`afb3dc7`** the `e00b1e3`/`371cbe5` blocklist (`PLACEHOLDER_FRAGMENTS`, example.com, 555-exchange positional match) was **deleted**. `validate_contact` at HEAD only rejects empty `name` / `email` / `phone`.

**Docs still claim a placeholder check:**

- CLAUDE.md command table: `db export-profile` “refuses to write a placeholder contact block, `--force` or not.”
- `cli.py` `--force` help and comments: “Does not bypass the placeholder check.”
- `application.py` comments still talk about diagnosing placeholder data in the DB, then call the weakened validator.

A database or `profile.json` holding `simon@example.com` / `555-555-5555` **passes** `validate_contact` and can export. `--force` only clobbers an existing destination file. Empty-field rejection and DB contact **cross-check** (mismatch, not shape) remain.

**Missing-file + empty-fields are live; placeholder *strings* are not.**

## Weakened / reversed

| Rule | Span | What happened |
|------|------|----------------|
| Gemini writes / generates resume text | `018f680` → `f3ca492` / `06e3587` | Prompt-era `b2224a7` was reorder-only; `generate.py` *did* author prose; slug selection replaced both. |
| Gemini-named PDF filenames | `f3ca492` → `da54f09` | Fixed `Simon_Chen_Resume.pdf`. |
| Sign-off loop | `06e3587` → `ba62443` | Deliver when `apply` succeeds. |
| `tailor --jd` | `f3ca492` → `06e3587` | Replaced by `--plan`. |
| Separate `archive` command | `ba62443` → `a84b998` | Subsumed by `apply` (~5 min coexist after `3df5a44`). |
| `tailor -f/--force` | `3df5a44` → `c42e91a` | Dead with archive. |
| `db sync` = export DB→profile | `99deed6` → `6640a8b` | Now seeds FROM profile; reverse is `db export-profile`. |
| `plans/` directory | `06e3587` → `c3e22a0` | Recoverable from git history only. |
| Plan↔archive consistency via `plans/` | `1e0c6f4` → `c3e22a0` | Tests dropped with the directory. |
| `resumes/` delivery mirror | LaTeX shop / `6ed0848` → `edeb27c` | Applications only. |
| Default eval PDF under `resumes/` | `1a32d53` → `edeb27c` | Latest `applications/*/Simon_Chen_Resume.pdf` or profile text. |
| GPA in resume | `2c8149a` → `6b52555` | Gate still scans output. |
| Optional `--jd` / empty-JD fallback | `ba62443` → `1e0c6f4` | Required + non-empty. |
| `load_profile` / seed fixture fallback | `dfa1022`/`85c6d1b` → `e74bcee`/`652ff4f` | Missing profile is fatal. |
| Placeholder *string* blocklist | `e00b1e3` → **`afb3dc7`** | **Weakened at HEAD** (see mismatch). |
| Same-day re-apply refused | `ba62443` → `e4f4cd2` | `_N` suffix instead of mutate-or-refuse. |
| Trim cuts recorded in `meta.json` | never on HEAD | `741b9a1` is on unmerged `fix/45-trim-loop-reports`. |

## Incident-derived chain (what actually remains)

1. Missing `profile.json` is fatal (`e74bcee`). Do not load `tests/fixtures/profile.json` for delivery. Never copy contact from the fixture at commits before `6640a8b` (real PII in git history; scrubbed same day `profile.example.json` was deleted).
2. Required contact fields must be non-empty at render/apply/seed/export (`e00b1e3`, still true after `afb3dc7`).
3. DB contact may be cross-checked against the profile (`371cbe5`); mismatch blocks. Shape/placeholder heuristics do **not**.
4. `seed_database` uses `load_profile`, not a parallel fixture path (`652ff4f`).
5. `export-profile --force` does not skip `validate_contact`; at HEAD that function is empty-fields only.

## Explicitly not invariants at HEAD

- Placeholder-string blocklist (`afb3dc7`). Non-empty `example.com` / 555 contact **passes** `validate_contact`.
- Argparse rejection of simultaneous `--jd -` and `--plan -` (unmerged `fix/cli-single-stdin-guard`).
- Trim-loop cut list in `meta.json` (unmerged `741b9a1` / tip `ae4837d`).
- Optimizer guardrails on hand-written `--plan`.
- Fixture fallback for missing `profile.json`.
- A tracked `plans/` or `resumes/` tree, `archive` CLI, Gemini in the compile path, Textual TUI, sign-off-before-deliver, Gemini-named employer PDFs.
- Unmerged `fix/*` (trim-loop reports, atomic export, extra evaluate/db fail-closed paths). Not shipped.

## Agent-only rules the optimizer will not save you from

Hand-written `--plan` files are not run through `apply_selection_guardrails()`. Persephone-first and the weak-project / personal-website / BU-IT gates are CLAUDE.md duties unless you omit `--plan`. One-page, filename, `--jd`, quality gates, contact non-empty, immutability, and gitignored delivery paths still apply either way.
