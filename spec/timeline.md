# Timeline (canonical)

Milestones across all eras (~42, not all 134 DAG commits / 69 first-parent). Dates are author
dates. **Reversals** are marked in place. “Landed” = the commit that introduced the behavior on
ancestry that reached HEAD. Two roots: `d78f844` (LaTeX shop) and `56767dc` (aggregator), joined at
subtree `191194d` (parents `56767dc`, `0af3a16`).

## Genesis (2025-09 → 2026-07-27)

LaTeX prompt shop → role-variant PDFs → JSON+Jake template, then a one-day job-aggregator root
absorbs that shop and immediately throws the aggregator away. A week of Gemini/TUI/over-engineering
collapses into a slug-keyed plan pipeline with CLAUDE.md. Slice ends at PR #1 (`11fe095`) with 12
tracked application folders. First-parent `56767dc`…`11fe095` inclusive: **29** commits.

**2025-09-19 `d78f844` — initalize**
LaTeX-shop root (one of two repository roots). Four files: `master_resume.tex` (**213** lines), empty
`ai_agent_prompt.txt` (0 bytes), `job_description.txt`, `tailored_resume.tex`. No compiler, JSON, or
Python. Same-day `48becca` adds `README.md` with `d78f844` as parent — not an accidental empty init;
the tex pair already existed. `git merge-base` with `56767dc` is empty: a true second root.

**2025-09-19 `b2224a7` — Add AI agent prompt for resume tailoring functionality**
First select-don't-write instinct, as prose to a LaTeX-editing agent (43 lines into the previously
empty prompt). Reorder experiences/projects/bullets; adjust Technical Skills only from text already
in the resume; do not change facts or structure. Workflow: paste JD into `job_description.txt`; emit
`tailored_resume.tex`. Same-day `74a4e60` / `820c164` tighten skills-sourcing rules. The invariant is
a prompt, not a slug resolver. The prompt is titled “Technical Recruiter AI” but **forbids writing
new content** — it does not author LaTeX from scratch. **Reversed** `17b1e90`. Superseded by the slug
pipeline (`06e3587`). Looking for `ai_agent_prompt.txt` is a year late.

**2025-09-27 `17b1e90` — Remove AI agent prompt … Clean up repository**
**Reversal:** deletes `ai_agent_prompt.txt` and `job_description.txt`. Root `master_resume.tex` /
`tailored_resume.tex` **rename into variants** (`R079` → `machine_learning_engineer_resume.tex`;
`R077` → `new_grad_software_engineer_resume.tex`); a **new** `resumes_latex/master_resume.tex`
joins them — **13** tex + 13 PDFs (12 role variants + master). Replaces the single-tailor flow with
role-variant `.tex` under `resumes_latex/` (backend, blockchain, quant, frontend, …). Tailoring
becomes “pick a pre-built variant and hand-edit.” `compile.sh` does not exist yet.

**2025-10-31 `de15db6` — added variations**
Consolidates `resumes_latex/` toward fewer variants: `backend_engineer_resume.tex`, fullstack,
mobile, master. The folder itself was born at `17b1e90`, not here. **Died** as a layout at
`0af3a16` (sources land in `src/*.tex`). Do not restore a multi-resume LaTeX tree.

**2025-10-31 `63b89ff` — added intern resumes**
Four `*_intern.tex` + PDFs (backend, fullstack, master, mobile). Dual intern/full-time PDFs lasted
~3.5 months until `2c8149a` collapsed the sprawl.

**2025-11-12 `f010d71` — Add self-hosted media and application server project**
Adds bullets naming Sonarr, Radarr, Prowlarr, Jellyfin, qBittorrent, Slskd (legacy PDFs / tex; no
`profile.json` yet). **Reversal later:** `d809428` rewords Slskd; `06e3587` purges the tooling from
`profile.json` and bans the names in `CLAUDE.md`; code gate `8c75336` (`gates.BANNED_TOOLS`).
Present in at least one tracked resume/JSON file from here until **`06e3587`** (not merely until
master tex dropped them). `cf5f217` (2025-12-31) strips blockchain/web3 from **`master_resume.tex`
only** — weak-project-gate precursor. **`5a91167` (2026-01-05)** drops fitness-tracker and
media-server from master tex only; intern/IT tex still had Sonarr/Slskd at that commit.

**2025-11-12 `da81003` — LinkedIn URL canonicalization**
`https://linkedin.com/in/shangmin-chen` → `https://www.linkedin.com/in/shangmin-chen` (display text
unchanged).

**2025-12-18 `a0e025d` — display name Shangmin → Simon**
Every `resumes_latex/*.tex` header `\textbf{\Huge \scshape Shangmin Chen}` → `Simon Chen`.
Email/GitHub/LinkedIn slugs stay `shangmin-chen`. Do not restore `Shangmin Chen` in `profile.json`
contact.name or TeX headers when archaeologying pre-December tex.

**2026-02-16 `2c8149a` — updated resume by adding gpa**
Adds `GPA: 3.53/4.0` on the full-time variant (internship variant: `GPA: 3.53`). Collapses
intern/full-time sprawl into `full_time_resume.tex` + `internship_resume.tex`. **Reversal:**
`6b52555` (2026-07-11). Commit messages never state why GPA was added. Gate still scans rendered
text even when the profile is clean (`8c75336`). (GPA in `profile.json` at `06e3587` is **3.58**,
not the 3.53 from this commit.)

**2026-06-20 `587f79f` — drop internship variant; Persephone/Hermes tightening**
Deletes `internship_resume.tex` / PDF. Splits Hermes first bullet; updates Persephone PnL. The
internship variant died **11 days before** `0af3a16` — do not assume intern vs full-time lasted until
the JSON restructure.

**2026-07-01 `0af3a16` — Restructure repository layout**
End state of the LaTeX-shop lineage (20 commits `d78f844`..`0af3a16` inclusive). **`resume.json`
still contains media-server, fitness-tracker, and ml-marketplace** after master tex removed them
(`cf5f217` / `5a91167`) — JSON resurrected what tex had dropped; real purge is **`06e3587`.**
`resume.json`,
`src/*.tex` (Jake's template), `compile.sh` (`latexmk` then; at HEAD it wraps `uv run python -m
worksisyphus compile`), `resumes/` outputs, ACLU CRM + cover-letter templates. `.agents/AGENTS.md`:
“Do not modify Jake's template” (it names `template/resume.tex`; the tex lives under `src/`). Author
date is **2026-07-01**, not 2026-07-06. This commit is the second parent of subtree `191194d`.
`compile.sh` is the first lasting entry point.

**2026-07-02 `56767dc` / `191194d` — Python root + subtree import of `job hunt/`**
Second root: a job-listing aggregator (`poll` / `normalize` / `enrich` / `catalog`), zero resume
code. Same package name, unrelated product. This is the **first-parent** root of main. `191194d`
subtree-merges `job hunt/` from `0af3a16` as second parent (verbatim `resume.json`, `src/*.tex`,
`compile.sh`, ACLU PDFs, AGENTS.md — **50** files in the tree). Two products coexist for exactly one
commit. After `6ed0848` the `job hunt/` prefix is gone — **do not resurrect those paths.** Resume
*content* archaeology walks the second parent.

**2026-07-07 `6ed0848` — Refactor repository to be a lightweight resume template builder**
**Reversal:** aggregator deleted (`src/worksisyphus/aggregator|normalizer|enricher|catalog`). `job
hunt/` flattened into `templates/` + `resumes/`. New `src/compile.py` renders JSON →
`Simon_Chen_Resume_Compiled.pdf`. Keeps ACLU templates and adds `junior_ai_cv.tex`. The Python repo
is now a resume compiler; the aggregator was a one-day detour. Dead forever:
`worksisyphus-aggregate*`.

**2026-07-07 `018f680` — Rename resume.json to experiences.json and add Gemini generator**
`src/generate.py` calls Gemini 2.5 Flash (`GEMINI_API_KEY`) to tailor resumes and cover letters from
JD text. Workflow shifts from editing JSON by hand to “AI generates, `compile.py` renders.” Values
are still mostly plain text. This **writes** tailored text — later forbidden. **Reversal:** Gemini
leaves the compile path at `06e3587`. `generate.py` vs later `planner.py` overlap is never documented
as an explicit decision. `generate.py` itself dies `f3ca492`.

**2026-07-07 `c8b2e27` / `8c83568` — Textual TUI; drop ACLU and junior_ai_cv**
`src/tui.py`: paste JD, generate, compile. **Dead end:** ACLU templates/PDFs deleted — no
replacement civic/CRM workflow in any commit. `8c83568` removes `junior_ai_cv` (does not return as a
slug) and makes `tex_files/` the single generated-tex directory (`resumes/` PDFs only). `tex_files/`
survives to HEAD. **TUI reversal:** `06e3587`.

**2026-07-08 `e57ff6a` / `2892302` — Deterministic compiler rewrite, then strip**
Birth of `src/worksisyphus/` (`profile.py`, `renderer.py`, `compiler.py`, `selection.py`, Gemini
`planner.py`, `benchmark.py`, tests, `docs/deterministic-compiler-plan.md`). **46** files;
`git show --numstat`: **7875** lines added. First named `bosch_resume.pdf`. Lasted ~1 day.
`2892302` drops the plan doc, `bosch_resume.pdf`, and stale tex. Over-engineering phase, not the
lean pipeline. Thin wrappers: `src/{compile,generate,tui,benchmark}.py`.

**2026-07-08 `0146d92` / `d809428` / `817734e` / `23e5426` — Verbatim TeX, sanitize Slskd, restore Persephone**
`0146d92`: JSON values become trusted TeX (`\$8K`, math macros); renderer stops escaping. `d809428`:
first employer-safe reword of the Slskd bullet (full piracy ban is `06e3587`). `817734e` /
`23e5426`: Persephone bullets lost in the JSON migration, restored from `job hunt` tex —
eight-bullet Python/Cython/C++17/Rust/Modal/FAISS line matching `191194d:job
hunt/src/Simon_Chen_Resume.tex`. Commit messages do **not** cite PDF kilobyte sizes; do not invent
them.

**2026-07-09 `f3ca492` — lean pipeline, one-page enforcement, first `cli.py`**
Deletes `benchmark.py`, artifact cache, `src/compile.py`, `src/generate.py`, most planner
complexity. Live commands: `compile`, **`tailor --jd`** (stdin `-` supported). Entry points:
`worksisyphus` **and** `worksisyphus-tui`. **`__main__.py` added** — `python -m worksisyphus` works
from here. `compile.sh` → `exec uv run python -m worksisyphus compile` (unchanged at HEAD).
`PAGE_LIMIT = 1` + `trim_step()` — first hard
one-page gate. Gemini `plan_selection()` + local render + trim loop until 1 page. Outputs named by
Gemini (e.g. `bosch_swe_ii_resume.pdf`). README: Gemini never writes resume text, only selects IDs.
Profile is still `templates/experiences.json`. Package TUI still exists for two days.
**Reversal of Gemini-named files:** `da54f09`. **`tailor --jd` dies** `06e3587`.

**2026-07-11 `06e3587` — Slug-keyed profile, plan-driven pipeline, agent conventions**
`profile.json` replaces `experiences.json` (slugs: `persephone`, `hermes-letters`, …). **30** files.
`plans/example.json` + `plan.py`; CLI `index`, `validate --plan`, `tailor --plan`. **`CLAUDE.md`
born:** one-page, Jake's template, select-don't-write, persephone-first, weak-project, BU IT,
sign-off, manual archive, never send the 3-page canonical. **Reversal:** `planner.py` and `tui.py`
deleted — no Gemini, no TUI, no `worksisyphus-tui` (`__main__.py` already existed from `f3ca492`).
`scripts/ats_check.py` added. Piracy tooling purged from content; ban list written into CLAUDE.md.
GPA still in the profile after this commit (`GPA: 3.58`, not the 3.53 from `2c8149a`). Sign-off
loop is written the same day and **reversed** at `ba62443`.

**2026-07-11 `6b52555` — Remove GPA from profile and rendered resumes**
**Reversal of `2c8149a`.** GPA gone from `profile.json` and canonical TeX. Permanent no-GPA rule;
`8c75336` later makes it a quality gate as well as a CLAUDE.md rule. Do not re-add a GPA for a form;
flag it to Simon.

**2026-07-11 `ba62443` / `da54f09` — Archive CLI; employer PDF name; drop sign-off**
`archive.py`: freeze `applications/<YYYY-MM-DD>_<stem>/` with `jd.txt`, `plan.json`, PDF,
`meta.json`. argparse: `--plan` + `--company` required; `--jd` optional default `""`. Two-step loop:
`tailor` then `archive`. **Reversal:** sign-off from `06e3587` replaced by “deliver when 1 page + ATS
pass.” First archives: `2026-07-09_bosch_software_engineer_ii`, `2026-07-11_fomo_labs_swe` (Bosch
later documented without `plan.json`, `18fda15`). `da54f09`: every employer-facing PDF is
`Simon_Chen_Resume.pdf`; plan stem names the folder only. **Reversal of Gemini-named outputs
(`f3ca492`).** **The `archive` command itself is reversed** `a84b998` when `apply` lands. Early
`applications/*/resume.pdf` names die around `643da17`.

**2026-07-12 `643da17` — Harden resume rendering and archive output**
`source_of_truth_resume.tex` extracted; renderer copies preamble verbatim — Jake's-template
invariant now in code, not only AGENTS.md. Archive copies renamed to `Simon_Chen_Resume.pdf`.
Horizontal overflow check added. Third application: `2026-07-12_greylock_techfair`. `ffa6cc2`
(2026-07-16) retitles Ezesports and adds `2026-07-16_ai_startups_sf`. **Never shrink margins/fonts
to fit.**

**2026-07-26 `5175332` — Add Personal Portfolio project and gate it to web-facing roles**
`personal-website` slug in `profile.json`; CLAUDE.md gate (frontend / full-stack / web-infra / edge
only; never quant/systems/backend/infra). Later encoded in the optimizer (`6640a8b`) when `--plan`
is omitted. Hand plans still bypass the optimizer.

**2026-07-27 `11fe095` — Fix GitHub URL, rename Ezesports to EZ Esports, regenerate archives (#1)**
Genesis terminus. **12** application folders: four already archived (Bosch, Fomo, Greylock,
AI-startups-SF) plus **eight** new dated Jul-18/26 (BlackRock, Evavi, BrightEdge, C3.ai, OOTD,
Palantir, Squoosh, TechForce). `plans/` holds matching JSON. GitHub URL was missing its hyphen
(`github.com/shangminchen` → `github.com/shangmin-chen`) **since the initial JSON profile**, so
every prior resume carried a dead link. **Regenerated every archived application PDF** from frozen
`plan.json` against then-current profile — a **one-time, explicit-user-request break** of archive
immutability (not a workflow). Rebuilds pulled in post-send profile drift, not a URL-only rewrite.
**Bosch** (no `plan.json`) and **Fomo** (legacy `"name"` key) could not be rebuilt. Canonical
recompile too. Workflow is still tailor → archive; `resumes/` and `plans/` still tracked.

## Productization (2026-08-02 → 2026-08-23)

August turns a local compiler into a product: required `--jd`, SQLite/Turso, CI, quality gates,
HackerRank evaluator, knapsack optimizer, then unified `apply`. Era ends when `resumes/` and
`plans/` are deleted so `applications/` (plus DB) is the only record. **64** DAG commits /
**37** first-parent in `11fe095..11a6ac2`.

**2026-08-02 `509d522` — Add tailored resumes for Jane Street, Google, Tasklet and 8 prior applications**
Bulk backfill of `applications/` plus matching `plans/`. Deletes stale Palantir/TechForce July
folders. Data dump, not a workflow change. Follow-on hygiene 2026-08-03: `a3f0039` (merged
`b3966fc`, #2) replaces Jane Street placeholder JD with the real posting; `c4914e9` (`0f776c4`, #3)
drops orphaned plans; `1476a55` (`bf2e4ee`, #4) strips invalid `"name"` from Fomo `plan.json`;
`18fda15` (`4ef3e06`, #5) annotates Bosch `jd.txt` as the known archive without `plan.json`.

**2026-08-05 `1e0c6f4` / `1314284` — Require --jd for archive; plan/archive consistency tests**
Merged `905d7d5` (#6). `archive --jd` is `required=True`; empty JD raises `ValueError` (no silent
`"No job description recorded."`). JD validated before mkdir so half-written folders cannot block
retries. `tests/test_consistency.py`: every `plans/*.json` except `example.json` matches an
application stem. CLAUDE.md gains “Deterministic enforcement over workflow instructions.” This
`--jd` flag is the ancestor of the same requirement on `apply`. Single-stdin is a later
counterexample still in prose (`docs-drift.md`).

**2026-08-05 `3ed9a69` / `21a3794` — Provenance sidecars and status CLI**
`tailor` writes `resumes/.provenance.json`; `archive` verifies PDF matches plan. New commands:
`status`, `update-status --app --status {applied|phone_screen|onsite|offer|rejected}`. No
`--no-sync` yet. `21a3794` (merged `7d383a6`, #9) hardens pdf_hash and fuzzy lookup. Ambiguous-stem
rejection is later (`e4f4cd2`). Mid-August batches (`d6d1c13`, `d715b78`, `868f8ab`/`ab0ed92`,
`8dd1442`, `730f1c8`, `60fbc04`) still use tailor→archive.

**2026-08-05 `64c0830` — `GEMINI.md`**
Antigravity mirror of agent rules. Integrated `5ce42b8` (#8). `git log --follow --diff-filter=A`
falsely reports `06e3587` (rename from CLAUDE.md). Without `--follow` the add is `64c0830`.

**2026-08-14 `310a65e` / `c76e53a` / `bdf8f2a` — JD via stdin; pdflatex discovery; plan-path rule**
Agents told to pipe JD with `--jd -` (`6a982ba` removes root temp JD files). Compiler checks PATH
and `/Library/TeX/texbin`; missing `pdflatex` fails with `brew install --cask mactex`. `bdf8f2a`
tests stdin paths for archive: `archive --plan -` **rejected** (`ValueError`; plan must be a path);
`--jd -` still OK; `validate --plan -` tested. The “path required for plans” half died with
`archive`; at HEAD both `--jd` and `--plan` accept `-` on `apply`. The “only one of `--jd`/`--plan`
may be `-`” rule is still **prose-only** — HEAD `cli.py` has no mutex.

**2026-08-18 `99deed6` — SQLite and Turso database layer with append-only audit trail**
Birth of `db.py`: `worksisyphus.db`, Turso push via `.env`, `db init|sync|status|history`. Seeds
profile + applications; `archive.py` hooks DB. **Invariant: db is a store, not a source** — render
path still reads `profile.json`. Initial **`db sync` called `export_profile_json` (DB → disk)** as
well as seed. **Semantics reversed** `6640a8b`: seed FROM `profile.json`, then push. Reverse path
becomes `db export-profile`. Same-day `83498e0` (connections, indexes) and `35d3a63` (clear
applications on reseed). `export-profile` is not a CLI yet. Turso sync is still ungated.

**2026-08-18 `8e89415` / `dfa1022` — Gitignore profile + applications; seed fixture fallback**
**Reversal:** tracked `applications/` and `profile.json` leave git. `8e89415` gitignores unanchored
`profile.json` and `applications/`; adds `profile.example.json`. `dfa1022` anchors `/profile.json`
`/applications/`, commits `tests/fixtures/profile.json`, and adds a **`seed_database` fixture
fallback** (CI convenience; hardening later treats it as a corruption vector). Local clone no longer
ships application history — Turso is the cloud mirror. Tests skip when `applications/` is empty.
`profile.example.json` is **deleted** `6640a8b` (README layout still lists it at HEAD).

**2026-08-18 `206ca02` / `c0abbcc` / `8c75336` / `35ad6d8` — CI, ATS module, quality gates**
`.github/workflows/ci.yml`: ruff, mypy, pytest 3.11/3.12 (no pdflatex). `ats.py` factored from
`scripts/ats_check.py` (script still exists). Author date of `c0abbcc` is **2026-08-18**, not
2026-08-19; it lives on first-parent **before** apply. `gates.py`: No-GPA, Banned Content, LaTeX
Leak, Content Density, ATS+page-count via `run_resume_gates()`. `35ad6d8`: DB folder set must match
`applications/` on disk. Gates are not yet wired into a single apply command. Circular validation
(gates vs the profile that rendered the PDF) is the hole `e74bcee` documents.

**2026-08-20 `1a32d53` / `97068bc` / `95e65f5` — Evaluator, optimizer, tailor lock**
HackerRank hiring-agent port (`evaluator.py`, `hiring_agent.py`, `roles/` + Jinja rubrics). CLI
`evaluate --app|--resume|--jd|--profile|--hackerrank|--check-upstream|--plan|--role` (`2d02657` adds
ETag caching via tracked `roles/upstream_manifest.json`; **`--check-upstream` always exits 0** —
`synced` / `outdated` / `untracked` / `rate_limited` / `cached`; HTTP/exception path is fail-open
`cached` / “offline verification passed”; corrupt local manifest is exit 1, not fail-open; see
unmerged `fix/hiring-agent-honest-upstream-status` / `fix/hiring-agent-cycle2-upstream-exits`).
Default resume **then** is
`resumes/Simon_Chen_Resume.pdf` — **reversed** `edeb27c`. `.provenance.json` sidecars die with
`resumes/` — do not restore them instead of the manifest.
`97068bc`: **`optimize --jd`** + **`evaluate --profile`**. Guardrails are not in `97068bc` yet — they
land in `6640a8b`. `95e65f5` (#19/#24): `resumes/.tailor.lock` — last major safeguard of the **old**
tailor→archive path (soon moot when `apply` stages atomically).

**2026-08-20 `3df5a44` / `a84b998` / `c42e91a` / `6564917` — Unified apply; delete archive**
Landing for PR #26 (`6564917`, 2026-08-21). `application.py` compiles into
`applications/<date>_<stem>/`, runs ATS, writes `meta.json`, syncs DB/Turso. CLI `apply --company
--jd [--role] [--url] [--plan] [--no-sync]`. **`3df5a44` (20:35:24 -0400)** adds apply; `tailor
-f/--force` added; **`archive` coexists ~5 minutes.** **`a84b998` (20:40:44 -0400) deletes `archive`
+ `archive.py`.** **`c42e91a` (21:08:34 -0400) deletes `tailor --force`**, unifies quality gates in
apply. After this day the agent workflow is `apply`, not tailor→ATS→archive. Same-day re-apply is
still `FileExistsError`. Tree at `3df5a44`: **120** files (`archive.py` + `application.py` both
present; `profile.example.json`, `plans/`, `resumes/`, `applications/` still tracked).

**2026-08-20 `85c6d1b` — `load_profile` fixture fallback**
Falls back to `profile.example.json` / fixtures when the default path is missing (CI). **This is
the fail-open `e74bcee` closes.** Chronology: `dfa1022` (Aug 18) → **`85c6d1b` (18:09)** →
**`6640a8b` (22:47, scrub/delete example)** → `e74bcee` / `652ff4f` (Aug 31) — not a
reintroduction after the incident fix. `85c6d1b` is an **ancestor** of `6640a8b`; the fallback
landed while the fixture still held live contact.

**2026-08-20 `6640a8b` — Atomic apply, coded guardrails, db sync FROM profile, delete example**
Atomic tempdir publish; `optimizer.apply_selection_guardrails()` encodes persephone-first /
weak-project / personal-website / BU-IT **in code when `--plan` is omitted**. **`profile.example.json`
deleted** (README layout still lists it at HEAD). **`tests/fixtures/profile.json` contact scrubbed**
to `simon@example.com` / `555-555-5555` (real contact replaced with placeholders — do not copy
pre-`6640a8b` fixture contact or the `652ff4f` message into tests). With `profile.example.json`
gone, `85c6d1b`'s remaining fallback was only the scrubbed fixture — causal step toward the Aug 31
incident. **`db sync` now seeds FROM `profile.json`**, then pushes; reverse path is
`export-profile`, not `db sync`.

**2026-08-20 `f553ff6` — `tailor` is PREVIEW only**
Help text + stdout `Preview build only - run worksisyphus apply`. `--output` (default `tex_files/`).
`plans/drafts/` appears here and **dies** with `plans/` at `c3e22a0`. A `tex_files/*.pdf` is not a
delivered resume from this commit onward.

**2026-08-21 `edeb27c` — delete resumes/ so applications/ is the only home for a delivered resume**
Merged `2a57152` (#42). **Reversal:** shared `resumes/` PDF gone. `build_canonical()` writes
`tex_files/`; `apply()` drops the mirror write. `evaluate` defaults to the newest application PDF
(else profile text). Commit documents the CI trade-off: no real PDFs in CI, so ATS/gate/evaluator
PDF tests skip there. `4320d04` drops the CI step that ATS-checked a **tracked** resume PDF (there
is none). Local pdflatex remains the only employer-PDF proof.

**2026-08-21 `f2165f3` — record the HackerRank evaluation with every application**
Successful `apply` writes `meta.json["evaluation"]` and DB `evaluation_json`. `backfill-evals
[--overwrite] [--no-sync]` for older folders. Commit body: **backfilled all 47 existing
applications**. **`synthesize_role_rubric` no longer writes files under `roles/`** — synthesis is
in-memory at HEAD; do not add role directories because a free-text `--role` used to. Evaluation is
part of the frozen record from here on.

**2026-08-23 `c3e22a0` — delete plans/ so applications/ and the DB are the only plan record**
Merged `11a6ac2` (#43). **Reversal:** deletes **46** plan JSON files (including `example.json`)
plus `plans/drafts/README.md`. Gitignores `/plans/` as a tombstone (issue #41). Plans become scratch inputs
(`$TMPDIR`); `apply` freezes `applications/.../plan.json`. Plan↔archive consistency tests that
walked `plans/` go away. Tree: **71** files. Era end. Still missing at this HEAD-of-era: `_N`
suffixes, git freshness gate, `contact_verification`, `export-profile` CLI. Recreating `plans/` in
the repo is a regression.

## Hardening (2026-08-24 → 2026-09-13 HEAD)

Fail-closed after silent fallbacks shipped wrong resumes or could corrupt the recovery DB.
First-parent after `11a6ac2` is only three merges (`5bf891e`, `3f23740`, `b654120`); landing commits
sit on merged feature branches (**21** commits in the full DAG). Unmerged `fix/*` is not this HEAD
(`docs-drift.md`).

**2026-08-24 `e4f4cd2` — same-day retry suffixes, unified resolver (#20)**
Merged `5bf891e` (#44, 2026-09-01). **Before:** second same-day apply refused; concurrent compiles
clobbered shared `tex_files/`; SQL `LIKE` treated `_`/`%` as wildcards; reverse-lexical “latest”
broke at `_10`. **After:** lowest free `_N` (`_2`, `_3`, …); `os.replace` + ENOTEMPTY retry so
published folders are never mutated; private temp tex dir per apply; `match_application_identifier`
is the one FS+DB grammar; numeric ordinal sort; status App# and `--company`. **Reverses
overwrite-refusal**, not folder immutability. `ee4c1da` documents a pre-#34 legacy-stem sort
limitation (a folder already ending in `_<digits>` can be mistaken for a retry ordinal). No
migration of old folder names.

**2026-08-31 `e74bcee` — fail loudly when profile.json is missing instead of loading the fixture**
Closes `85c6d1b` on the load path. Commit body is the source for the incident: `load_profile`
silently used `tests/fixtures/profile.json` when gitignored `profile.json` was absent; the fixture
is a full profile with contact scrubbed to `simon@example.com` / `555-555-5555`; **four applications
were built and sent**; every quality gate passed because gates compared the PDF to the same profile
that rendered it. Missing profile is now `FileNotFoundError` naming `db export-profile`. CLI adds
that command (`--output`, `--force`). The four folder names are not in the commit; do not invent
them. Recovery path is the database, not `git checkout`. Tests cover both halves: `load_profile()`
must raise even with a fixture present.

**2026-08-31 `9923c95` — never return a plan the optimizer did not score**
Merged `201fc80`. Unscored first-candidate fallback and a degenerate `<2 projects` bypass of
guardrails are gone. Zero scored candidates → `OptimizerError` (CLI exit 1). Plan-less `apply` can
no longer ship an arbitrary config. Partial failures surface in `candidate_failures` / stderr WARN.

**2026-08-31 `e00b1e3` / `371cbe5` — placeholder/missing contact unbuildable, then remaining holes**
Merged `0d526f7`, `ab4316b`. Interim `validate_contact`: non-empty name/email/phone **and** a
placeholder blocklist (example.com, 555 exchange, positional NANP). `render_resume` / `apply`
validate before pdflatex; `require_contact=True` on delivery gates; DB cross-check against the
contact row. `371cbe5`: `tailor` no longer bypasses validation; `contact_verification` frozen into
`meta.json` (`rules_checked`, `cross_checked_against_db`, `skip_reason`); positional 555 matching;
symlink-aware path resolve so cross-check is not silently skipped. **Exception:** `backfill-evals`
still degrades if profile is missing. Pre-this-day folders omit `contact_verification` (“not
recorded”). Do not invent a count of those folders (`applications/` is gitignored at HEAD).

**2026-08-31 `652ff4f` / `dab87a5` — seed must not invent a profile; validate content not just the file**
Merged `aa21546`, `663b2be`. `seed_database` had its **own** fixture fallback (did not call
`load_profile`), so missing `profile.json` on `db sync`/`init`/`backfill-evals` could overwrite
SQLite + Turso, then `export-profile` write placeholders back. Invisible to greps for
`load_profile(`. After: seed via `load_profile` + `profile_to_dict`; missing profile raises
**before** `init_schema`; `export_profile_json` runs `validate_contact`; `--force` only clobbers.
Failed seed on a fresh DB leaves no tables. `dab87a5`: an on-disk placeholder `profile.json` also
fails seed (blocklist half later removed). Directional hints: DB good → export; profile good →
`db sync`.

**2026-09-01 `afb3dc7` — remove placeholder blocklist and simplify contact validation**
**Reversal of the Aug 31 blocklist.** −554/+85 across profile/db/application/tests.
`validate_contact` at HEAD checks only that `name`, `email`, `phone` are non-empty.
Seed/export/cross-check still call it, so they no longer reject `example.com` or 555 numbers.
`3f23740` (merge #48) integrates this with the rest of the fail-closed stack. PR title still says
“placeholder”; the protection that actually merged is **missing file + empty required fields**.
CLAUDE.md and CLI `--force` help were not updated (`docs-drift.md`).

**2026-09-01 `39fad80` / 2026-09-13 `e92de45` / `b654120` — Turso git freshness gate, then fail-closed**
`git_guard.py`: sync (`apply`, `update-status`, `backfill-evals`, `db sync`/`init`) only from `main`
(or `--allow-branch` on a **named** non-main branch), best-effort fetch, block if behind
`origin/main`. Flags: `--no-sync`, `--allow-branch`, `--no-git-check`. `39fad80` was fail-open on
missing upstream / detached HEAD; `e92de45` closes remaining fail-open: detached HEAD always
blocked; missing/unreadable `origin/<target>` refuses sync. “Could not verify” is not “sync anyway.”
`b654120` is HEAD (merge #51). This `docs/spec-timeline` branch will skip Turso unless those flags
are passed — that is intended.

**Not on HEAD:** `741b9a1` (2026-09-13) “record each trim-loop cut in logs and `meta.json`” lives
only on `fix/45-trim-loop-reports` (current tip `ae4837d`). HEAD `pipeline.py` logs
`"{n} pages; trimming and recompiling..."` without naming the cut. README’s “deliver what the trim
loop cut” is aspirational relative to HEAD.
