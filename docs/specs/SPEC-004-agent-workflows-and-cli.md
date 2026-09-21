# SPEC-004: Agent Workflows, CLI Registry & Operational Rules

| Field | Value |
|---|---|
| **Spec ID** | `SPEC-004` |
| **Title** | Agent Workflows, CLI Registry & Operational Rules |
| **Status** | `Active` |
| **Author** | Simon Chen / LLM Agent Synthesis |
| **Created** | 2026-09-13 |
| **Updated** | 2026-09-21 |
| **Supersedes** | None |
| **Superseded By** | None |
| **Related Issues/PRs** | PR #86, PR #88 |

---

# Agent workflow by era + HEAD command registry

What an agent was supposed to do. **Current HEAD workflow is the last live section plus the command registry.** Do not run the earlier ones. Exit **0** success, **1** with `error: <message>` on stderr. Plan errors name the slug.

## Entry points (HEAD)

| Invocation | Since | Notes |
|------------|-------|-------|
| `uv run worksisyphus <cmd>` | `f3ca492` | `[project.scripts]` → `worksisyphus.cli:main` |
| `python -m worksisyphus <cmd>` | `f3ca492` | `__main__.py` |
| `./compile.sh` | `0af3a16` | Thin wrapper; since `f3ca492` execs `uv run python -m worksisyphus compile` |
| `uv run --with pdfminer.six python scripts/ats_check.py <pdf>` | `06e3587` | Manual ATS; apply/CI use in-process `ats.py` |

## Era-by-era agent workflow

### Sep 2025 — reorder LaTeX (`b2224a7`–`17b1e90`)

Read `ai_agent_prompt.txt`. Paste JD into `job_description.txt`. Reorder `master_resume.tex` into `tailored_resume.tex`. Cannot change facts, structure, or bullet wording. No build script. Dead after `17b1e90`.

### Oct 2025 – Jun 2026 — pick a variant (`17b1e90`–`0af3a16`)

No agent prompt. Choose a role-variant `.tex` under `resumes_latex/`, hand-edit, compile externally.
**`63b89ff` (2025-10-31):** four `*_intern.tex` + PDFs join the full-time variants. **`2c8149a`
(2026-02-16):** collapses to `full_time_resume.tex` + `internship_resume.tex` (GPA 3.53).
**`587f79f` (2026-06-20):** deletes the internship variant — 11 days before `0af3a16`. **`a0e025d`
(2025-12-18):** display name Shangmin → Simon in tex headers; slugs stay `shangmin-chen`. Do not
restore `Shangmin Chen` when archaeologying old tex. `./compile.sh` appears at `0af3a16` with
`resume.json` + `src/*.tex`. AGENTS.md: do not modify Jake's template.

### 2026-07-02 — aggregator detour (`56767dc`–`191194d`)

Wrong product. Four separate console scripts: `worksisyphus-aggregate`, `worksisyphus-normalize`,
`worksisyphus-enrich`, `worksisyphus-catalog`. Resume shop sits in `job hunt/` for one commit,
unused by that CLI.

### 2026-07-07 morning — JSON compile + optional Gemini (`6ed0848`–`018f680`)

Edit `templates/resume.json` / `experiences.json`. `./compile.sh` or `python src/compile.py`. Optional: `python src/generate.py` with `GEMINI_API_KEY` for JD-based generation (this **writes** tailored text — later forbidden).

### 2026-07-07 afternoon — TUI (`c8b2e27`–`8c83568`)

`uv run worksisyphus-tui` / `python src/tui.py`. Paste JD. Outputs land in `tex_files/` + `resumes/`.

### 2026-07-08–09 — Gemini tailor CLI (`e57ff6a`, `f3ca492`)

`uv run worksisyphus tailor --jd jd.txt` (stdin `-` supported). Gemini returns a JSON selection plan (and, after `f3ca492`, the output filename). Local deterministic render + trim until 1 page. README at `f3ca492`: Gemini never writes resume text, only selects IDs. TUI still exists. **`tailor --jd` dies** `06e3587`.

### 2026-07-11 – ~2026-08-20 — plan files + tailor + archive (`06e3587`–pre-`3df5a44`)

Gemini and TUI are gone. CLAUDE.md is the contract.

1. `uv run worksisyphus index`
2. Write `plans/<company>_<role>.json` (order = rank)
3. Optional `validate --plan`
4. `tailor --plan` → **`resumes/Simon_Chen_Resume.pdf`** (shared file; next tailor overwrites)
5. `scripts/ats_check.py` (later in-process ATS)
6. Deliver that PDF
7. `archive --plan … --company …` into `applications/<YYYY-MM-DD>_<stem>/`

Sign-off loop exists only between `06e3587` and `ba62443`; after that, deliver when 1 page + ATS pass.

**From `1e0c6f4` (2026-08-05):** `--jd` is required on archive; empty JD is an error. **From `310a65e`:** pass JD via `--jd -`, do not write `jd.txt` at repo root. **From `bdf8f2a`:** `archive --plan -` **rejected** (plan must be a path). **From `3ed9a69`:** provenance sidecars; `status` / `update-status`. **From `95e65f5`:** `resumes/.tailor.lock` — archive before the next tailor. **From `99deed6`:** `db sync` exists but does not feed the renderer. Plans in `plans/` must match applications (`test_consistency.py`); WIP lived in `plans/drafts/` (`f553ff6`) until that dir vanished with `plans/`.

Bosch (`2026-07-09_bosch_software_engineer_ii`) is the documented pre-convention archive without `plan.json` (`18fda15`).

### 2026-08-20 onward — unified apply (HEAD)

`archive` is deleted (`a84b998`; coexisted ~5 minutes after `3df5a44`). `resumes/` is deleted (`edeb27c`). `plans/` is deleted (`c3e22a0`). `tailor` remains as a **preview** into `tex_files/` (`f553ff6`) and does not write `applications/`, run ATS, or sync Turso. Delivery is one command.

```bash
uv run worksisyphus index
# compose plan in scratch — not in the repo
#   $TMPDIR/<company>_<role>.json
cat "$plan" | uv run worksisyphus validate --plan -   # optional
cat << 'EOF' | uv run worksisyphus apply --company <Company> --jd - [--role <Role>] [--url <url>] [--plan "$plan"]
<Pasted JD text>
EOF
```

Rules an agent at HEAD must not skip:

- **`--jd` is required.** Use `--jd -` for pasted text. If there is no posting, pipe a note explaining why; the command refuses empty JD.
- **Only one of `--jd` / `--plan` should read stdin** (documented in CLAUDE.md / GEMINI.md / README). HEAD `cli.py` does **not** enforce this; both arguments independently call `sys.stdin.read()` via `_read_plan`. Unmerged `fix/cli-single-stdin-guard` is not shipped. If both are `-`, the second read is empty. When JD is `-`, pass the plan by path.
- **`--plan` optional.** Omitted → knapsack optimizer with coded selection guardrails. Prefer writing the plan when the JD needs judgment the rubric cannot express. Hand `--plan` **bypasses** `apply_selection_guardrails()`.
- **Scratch plans.** There is no `plans/` directory. `apply` freezes the exact plan into `applications/<YYYY-MM-DD>_<stem>/plan.json` and Turso.
- **Done when `apply` exits 0** (1 page, horizontal overflow only if overfull **> 2pt**, ATS, No-GPA, banned content, LaTeX leaks, density ≥350 words / 1500 chars). No sign-off. PDF exists only at `applications/<folder>/Simon_Chen_Resume.pdf`. Filename is never company-slug'd. **Exit 0 does not prove SQLite/Turso recorded the send** — no `worksisyphus.db` → folder publishes with no DB row; Turso skips warn only.
- **Omitted `--role`:** folder stem uses `swe`; plan-less optimizer and evaluation rubric default to `software_engineer`. Pass `--role` if the folder name should reflect the job title.
- **Same-day retry** allocates `_2`, `_3`, … (`e4f4cd2`). Do not mutate a published folder. Update only `meta.json.status` via `update-status`.
- **`tailor --plan` is preview** into `tex_files/`. Never send that PDF. Never send `Simon_Chen_Resume_Compiled.pdf`.
- **Missing `profile.json`:** do not copy the test fixture. Recover with `uv run worksisyphus db export-profile [--force]`. If the profile is good and the DB is stale, `db sync` — not export.
- **Turso git gate** (`39fad80`, fail-closed `e92de45`): default sync only on `main`, upstream verifiable, not behind `origin/main`. `--no-sync` skips cloud; `--allow-branch` allows a **named** non-main branch; `--no-git-check` skips the gate. Detached HEAD cannot sync. Cloud sync from this `docs/spec-timeline` branch will be skipped unless those flags are passed — that is intended.
- **Optimizer failure** is exit 1 (`OptimizerError`); do not invent a plan to “just apply.”
- **Contact:** HEAD rejects empty name/email/phone, not placeholder strings (`afb3dc7`). Do not load `tests/fixtures/profile.json` for delivery — production `load_profile` never does; **`tests/conftest.py` `real_profile` still falls back to the fixture for CI only.** **`apply` cross-checks all six contact fields against the DB before pdflatex** when `worksisyphus.db` exists (`371cbe5`); mismatch blocks. No DB file skips cross-check, insert, and Turso — do not delete the DB to “unblock,” and do not treat exit 0 as “DB verified.”
- **Fixture archaeology:** never copy contact from `tests/fixtures/profile.json` at commits before `6640a8b` (real PII in git history).

`evaluate` / `optimize` / `backfill-evals` / `db status|history|init` are supporting tools, not the delivery path. `backfill-evals` scoring tolerates missing profile for labels (`e00b1e3`); the CLI then always `seed_database()`, which **raises** if `profile.json` is missing — a fresh clone without profile fails at seed, not only at scoring.

## Live commands at HEAD

### `compile`

Rebuild canonical 3-page `Simon_Chen_Resume_Compiled.pdf` (database view). **Flags:** none. **Never** send to employers.

### `index`

Print every selectable slug with bullet text. **Flags:** none. Needs `profile.json`.

### `validate --plan <file|->`

Parse + resolve slugs; no LaTeX. **Required (argparse):** `--plan`. **Stdin:** `--plan -`.

### `tailor --plan <file|-> [--output <dir>]`

**PREVIEW ONLY** into `tex_files/` (or `--output`). **Required:** `--plan`. Prints `Preview build only - run worksisyphus apply`. **Never** writes `applications/`, ATS, Turso. **Removed:** `-f/--force` (`c42e91a`).

### `apply --company <name> --jd <file|-> [--role] [--url] [--plan <file|->] [--no-sync] [--allow-branch] [--no-git-check]`

1-step deliver: validate + DB contact cross-check (before compile) → compile → gates/ATS → freeze `applications/<YYYY-MM-DD>_<stem>/` (`jd.txt`, `plan.json`, `Simon_Chen_Resume.pdf`, `meta.json` with `contact_verification`) → DB insert (only if `worksisyphus.db` exists) → optional Turso (skips warn). Records HackerRank eval.

- **Argparse required:** `--company`, `--jd`.
- **Code required:** non-empty `jd_text` (`application.py` `ValueError`).
- **`--plan` omitted:** knapsack + `apply_selection_guardrails`. **`--role` omitted:** folder stem `…_swe`; optimizer rubric `software_engineer`.
- **Stdin:** `--jd -` and `--plan -` each call `_read_plan` → `sys.stdin.read()`. **If both are `-`, the second read is empty.** CLAUDE.md/GEMINI.md/README say only one may be `-`. **HEAD `cli.py` has no guard** (no dual-`-` check).
- Same-day retry → `_2`, `_3`, … (`e4f4cd2`).

### `status [--company <substring>]`

List date, company, role, status, App# (repeat applicants), folder. Case-insensitive company filter. **`status --company` is in README intro prose; CLAUDE.md’s command table lists `status` with no filter flag.**

### `update-status --app <folder|stem> --status <status> [--no-sync] [--allow-branch] [--no-git-check]`

Mutate `meta.json.status` only. **Required:** `--app`, `--status` (`applied`, `phone_screen`, `onsite`, `offer`, `rejected`). Ambiguous stems → error listing matches.

### `backfill-evals [--overwrite] [--no-sync] [--allow-branch] [--no-git-check]`

Score applications that predate eval recording; re-seed DB; optional Turso.

### `evaluate` (modes, not mutually exclusive in argparse)

| Mode | JD? | Behavior |
|------|-----|----------|
| `--check-upstream` | no | Reads `roles/upstream_manifest.json`; ETag check is return-value only (manifest not rewritten). Statuses: `synced`, `outdated`, `untracked`, `rate_limited`, `cached`. HTTP/exception → **`cached` / “offline verification passed”** (fail-open); corrupt local manifest → exit 1. **CLI always exits 0** for every status including `outdated`/`untracked`/`cached` — not proof of sync. Unmerged honest-upstream branches would change this. |
| `--app <folder\|stem>` | from `jd.txt` | Score that app's PDF |
| `--profile` | unless `--hackerrank` | Score full profile text (no PDF) |
| `--resume <pdf> --jd <file\|->` | yes | Arbitrary PDF |
| `--plan <file\|-> --jd <file\|->` | yes | Plan-resolved text (**in CLI; omitted from CLAUDE/README tables**) |
| no flags | yes unless `--hackerrank` | Latest application PDF, else profile text |
| `--hackerrank` | optional | 1:1 HackerRank; `--role` (default `software_engineer`) |

`--role` on **evaluate** is consumed only by `--hackerrank`. `optimize` and `apply` (optimizer path) have their own `--role`.

JD rule in code: required unless `--app`, `--hackerrank`, or `--check-upstream`.

### `optimize --jd <file|-> [--role] [--output <file>]`

Knapsack search; optional write plan JSON. **Required:** `--jd`. Uses coded selection guardrails.

### `db init|sync|status|history|export-profile`

| Subcommand | Purpose | Git sync flags |
|------------|---------|----------------|
| `init` | Seed SQLite from `profile.json` + `applications/`, push Turso | `--allow-branch`, `--no-git-check` only (no `--no-sync`) |
| `sync` | Re-seed from `profile.json`, push Turso | `--allow-branch`, `--no-git-check` only (no `--no-sync`) |
| `status` | Metrics + connection | no |
| `history [--limit] [--type]` | Audit trail | no |
| `export-profile [--output] [--force]` | DB → `profile.json`. `--force` clobbers destination only | no |

At HEAD `init` and `sync` both call `seed_database` then `sync_to_turso` (messaging differs). **`db init` is missing from CLAUDE.md/README command tables.** `db history --type` exists; docs only mention `--limit`. Export's remaining check is non-empty contact, not placeholder strings (`afb3dc7`), despite `--force` help text.

## Dead commands and replacements

| Command | Lived | Now | Use instead |
|---------|-------|-----|-------------|
| `worksisyphus-aggregate` / `-normalize` / `-enrich` / `-catalog` | `56767dc`–`6ed0848` | gone | N/A |
| `worksisyphus-tui` / `python src/tui.py` | `c8b2e27`/`f3ca492`–`06e3587` | gone | `apply` / `tailor` / `index` |
| `python src/generate.py --jd …` | `018f680`–`f3ca492` | gone | `apply` or hand plan + `apply --plan` |
| `tailor --jd <file\|->` | `f3ca492` only | flag gone | plan JSON, then `tailor --plan` or `apply` |
| `archive --plan … --company … --jd …` | `ba62443`–`a84b998` | gone | `apply` |
| `archive --plan -` | never (rejected `bdf8f2a`) | — | plan file path |
| `tailor -f/--force` | `3df5a44`–`c42e91a` | gone | `apply` |
| `db sync` exporting DB→profile.json | `99deed6`–`6640a8b` | flipped | `db sync` seeds FROM profile; `db export-profile` for reverse |
| Default eval `resumes/Simon_Chen_Resume.pdf` | `1a32d53`–`edeb27c` | `resumes/` deleted | latest application PDF or `--profile` |

## Enforcement vs prose (CLI)

| Constraint | Where |
|------------|--------|
| Subcommand required | argparse `required=True` on subparsers |
| `--company`, `--jd` (apply), `--plan` (validate/tailor), `--app`, `--status` | argparse `required=True` |
| Empty JD on apply | `application.py` `ValueError` |
| Unknown slug | `plan.py` `PlanError` |
| One-page / overflow (>2pt) / five gates (+ density floors) | pipeline + gates during apply |
| `tailor` never delivers | writes `PREVIEW_DIR` only |
| `--jd`/`--plan` single-stdin | **prose only** (CLAUDE.md, GEMINI.md, README). **Not in `cli.py` at HEAD.** |
| Selection guardrails | optimizer; **not** `validate`/`apply --plan` |
| Turso git gate | `git_guard.py`; `--allow-branch` / `--no-git-check` |
| Employer filename | pipeline, not a flag |
| Placeholder *strings* on export | **docs claim code; HEAD only checks non-empty fields** |

## Failure modes agents hit at HEAD

- Missing `profile.json` → `FileNotFoundError`, not a fixture resume. Recover, then retry apply.
- Empty contact fields → `validate_contact` ValueError at render/apply/seed/export. Placeholder strings with non-empty fields do **not** fail (`afb3dc7`).
- Optimizer total failure → `error: …` on stderr, exit 1. Do not hand-wave a plan unless you actually write `--plan`.
- Target folder race → `_N` suffix, not overwrite (`e4f4cd2`).
- Turso skipped because this branch is not `main` (e.g. `docs/spec-timeline`) → expected. Use `--no-sync` if you meant to stay local; do not pass `--no-git-check` unless the user asked.
- No `worksisyphus.db` on disk → `apply` still publishes the folder but skips SQLite insert, Turso, and contact cross-check. Exit 0 is not “recorded in DB.”
- `evaluate --check-upstream` exit 0 with `cached`/`outdated`/`untracked` → informational only; run `db init`/`sync` separately if you need a contact row for cross-check.
- `tailor` output in `tex_files/` looking “done” → it is a preview. Employers get `applications/.../Simon_Chen_Resume.pdf` from `apply` only.
- CLAUDE.md asking you to report trim-loop cuts → the pipeline does not persist them at HEAD (`fix/45-trim-loop-reports` unmerged). Say what you ranked last (trim order is bottom of the plan) rather than inventing a cut log.
- Both `--jd -` and `--plan -` → second stdin read is empty. Pass the plan by path.

## What not to write to the repo

Do not create `plans/`, `resumes/`, `jd.txt` at repo root, or `profile.example.json`. Do not commit `profile.json` or `applications/` (gitignored). Do not resurrect `archive.py`, TUI, or Gemini planner. Do not edit `source_of_truth_resume.tex` to fit a page.
