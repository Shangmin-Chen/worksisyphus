# worksisyphus — Agent Instructions

You are operating Simon Chen's resume compiler. Given a job description, your job is to find the best combination of content from `profile.json`, write a plan file, and produce a tailored one-page PDF.

## Bounded rules (never violate)

1. **One page.** Every resume delivered to the user must compile to exactly 1 page. The pipeline's trim loop enforces this mechanically; never bypass it, and never deliver a multi-page tailored PDF.
2. **Jake's template formatting.** Formatting lives in `source_of_truth_resume.tex`. At build time the renderer copies its preamble verbatim, replaces only the body in memory, and never modifies the source file. Never modify the LaTeX preamble, section styles, or spacing to squeeze content in — fit is achieved by selecting less, not by shrinking margins or fonts.
3. **Best combination for the JD.** Selection is your judgment call: read the job description, then pick the experiences, projects, bullets, and skills that best match it. Rank order in the plan is relevance order — the trim loop cuts from the bottom, so put the most JD-critical items first.
4. **Select, propose, never write.** You choose slugs; you do not author resume content. If a JD genuinely begs for a reworded or new bullet, you may PROPOSE the exact text to the user, but you must never edit `profile.json` without their explicit approval of that specific text. This is the core guarantee of the system: a plan can omit a bullet, never corrupt one.

## Selection guardrails

- **Every employer-facing resume is named `Simon_Chen_Resume.pdf`** — recruiters see the filename, and it must never look auto-generated (no company slugs, no "tailored", no version suffixes). The pipeline enforces this; never rename the output. Per-application copies live in `applications/`, identified by their folder name. The 3-page canonical (`Simon_Chen_Resume_Compiled.pdf`) is the only differently-named PDF and never goes to employers.
- **Never include a GPA** in `profile.json`, rendered TeX, or any resume output — Simon has decided it does not strengthen his profile. If a JD or application form explicitly demands a GPA, do not add it to the resume; flag it to Simon and let him handle it outside the pipeline.
- **Never send the canonical resume to an employer.** `Simon_Chen_Resume_Compiled.pdf` (3 pages) is the database view for Simon's own reference. Employers only ever get tailored one-pagers.
- **Persephone-first for engineering roles.** Any backend, systems, infra, performance, or quant JD ranks `persephone` as the top project unless the JD clearly contradicts it (e.g. a pure frontend or mobile role).
- **Weak-project gate.** `fitness-tracker`, `spark-food-waste`, and `ml-marketplace` only appear when the JD directly matches them (mobile role, civic/impact org, blockchain role respectively). Never use them as filler.
- **Personal-website gate.** `personal-website` only appears for frontend, full-stack, web-infra, and edge/serverless JDs. A portfolio site is the most common project on a new-grad resume, so it weakens any resume where `persephone` and `hermes-letters` already carry the engineering signal — never select it for quant, systems, backend, or infra roles.
- **BU IT gate.** `bu-engineering-it` is only selected for IT/support/security-adjacent JDs, never for pure SWE roles.
- No numeric caps on picks — the one-page constraint plus your ranking does the shaping.

## Workflow for "tailor my resume to this JD"

1. `uv run worksisyphus index` — see every selectable slug with full bullet text.
2. Compose the plan JSON yourself (order = rank; format in README "Plan files"). Plans are **inputs,
   not artifacts**: there is no `plans/` directory. Write it to scratch outside version control
   (e.g. `$TMPDIR/<company>_<role>.json`) — `apply` freezes the exact plan into
   `applications/<YYYY-MM-DD>_<stem>/plan.json` and syncs it to Turso, which is the record.
3. Optional pre-flight: `cat <plan> | uv run worksisyphus validate --plan -` catches unknown slugs
   without compiling (`apply` validates too, so this step is skippable).
4. **Apply (1-step compile, ATS check, freeze & Turso sync):**

   ```bash
   cat << 'EOF' | uv run worksisyphus apply --company <Company> --jd - [--role <Role>] [--url <posting url>] [--plan <scratch plan file>]
   <Pasted JD text>
   EOF
   ```

   `--plan` is optional. When omitted, `apply` runs the knapsack optimizer to choose the plan for
   you; the optimizer enforces the selection guardrails above (weak-project, personal-website,
   BU IT, persephone-first) in code. Prefer writing the plan yourself when the JD needs judgment
   the rubric cannot express. Add `--no-sync` to skip the Turso push.

   `--jd` is **required**. Pass the user's pasted JD via stdin (`--jd -`) to avoid leaving temporary files in the repository root. If there is genuinely no JD (internal referral, career fair), pass a note explaining the absence (e.g. "Internal referral — no formal job description.") via stdin. The command refuses empty JD text.
   Only one of `--jd`/`--plan` may read stdin at a time: when the JD comes via `-`, pass the plan by file path (and vice versa).

   This creates `applications/<YYYY-MM-DD>_<app-stem>/` with `jd.txt` (verbatim posting), `plan.json`, `Simon_Chen_Resume.pdf`, and `meta.json` (`company`, `role`, `date`, `source_url`, `status: "applied"`, `evaluation` — the HackerRank hiring-agent score for the resume as sent — and `contact_verification`, recording whether the contact block was cross-checked against the database and, if not, why; folders published before that field existed simply omit it, which reads as "not recorded"), runs the ATS extraction check, inserts into `worksisyphus.db` (including `evaluation_json`), and automatically syncs to Turso cloud. The resume is compiled directly into that folder and written nowhere else — `applications/` is the only place a delivered resume exists on disk.

5. **Deliver.** The resume is done when `apply` succeeds (compiles to exactly 1 page AND has no horizontal overflow AND passes all quality gates: ATS, No-GPA, Banned Content, LaTeX Leaks, Content Density) — no user sign-off is required. Send the PDF along with what was picked, why, and exactly what the trim loop cut (if anything).

   Application folders are immutable history: never modify an application's `Simon_Chen_Resume.pdf` or `plan.json` — a re-application to the same company gets a new dated folder (the command refuses to overwrite). Update only `meta.json.status` (and `meta.json.evaluation`, via `backfill-evals`) when the user reports progress (`applied` → `phone_screen` / `onsite` / `offer` / `rejected`). Questions like "which applications are still open?" are answered by reading `applications/*/meta.json` or `uv run worksisyphus status`.

## Editing profile.json (only with approval)

- Values are trusted TeX inserted verbatim: escape `$`, `%`, `&`, `#` (`\$8K`, `75\%`), math like `$\sim$20$\mu$s` is intentional.
- Slugs are stable identifiers — never rename a slug casually; plans reference them.
- Every metric must be defensible in an interview. Never add a number the user didn't state.
- Banned content (removed deliberately, do not reintroduce): piracy-adjacent tooling names (Sonarr/Radarr/Prowlarr/Jellyfin/qBittorrent/Slskd/Soulseek), fake-smelling metrics ("uptime by 15%", "100% incident resolution"), keyword-stuffed skills.

## Commands

```bash
uv run worksisyphus apply --company <name> --jd <file|-> [--role <role>] [--url <url>] [--plan <plan>] [--no-sync]  # 1-step compile, validate, freeze & Turso sync
uv run worksisyphus compile                      # canonical 3-page database view (never for employers)
uv run worksisyphus index                        # list all selectable slugs
uv run worksisyphus validate --plan <file|->     # parse + resolve a plan, no LaTeX needed
uv run worksisyphus tailor --plan <file|-> [--output <dir>]  # PREVIEW build into tex_files/ (never delivers; use apply)
uv run worksisyphus status                       # list all applications and their status
uv run worksisyphus update-status --app <name> --status <status>  # update status & auto-sync to Turso
uv run worksisyphus evaluate --app <name>        # evaluate & score an application against its JD
uv run worksisyphus evaluate --resume <pdf> --jd <file|->  # score any resume against a JD
uv run worksisyphus evaluate --profile [--jd <file|->] [--hackerrank]  # evaluate the full profile.json canonical database directly
uv run worksisyphus evaluate --hackerrank [--role <role>]  # 1:1 HackerRank evaluation
uv run worksisyphus evaluate --check-upstream        # check sync status against upstream interviewstreet/hiring-agent
uv run worksisyphus optimize --jd <file|-> [--role <role>] [--output <file>]  # combinatorially find highest-scoring plan for a JD
uv run worksisyphus backfill-evals [--overwrite]  # score applications that predate evaluation recording
uv run worksisyphus db status                    # show database overview, metrics, and connection status
uv run worksisyphus db history [--limit N]       # show append-only timestamped audit trail
uv run worksisyphus db sync                      # load profile.json into SQLite and push to Turso cloud
uv run python -m pytest tests/ -q               # test suite (no network, no pdflatex needed)
uv run --with pdfminer.six python scripts/ats_check.py <pdf>   # ATS extraction check
```

> **Prerequisite:** MacTeX (or BasicTeX) is required for `pdflatex` compilation: `brew install --cask mactex`. The compiler automatically checks PATH and `/Library/TeX/texbin` and fails with an explicit error if missing.

Exit codes: 0 success, 1 failure with a one-line `error: ...` on stderr. Plan validation errors name the offending slug.

## Deterministic enforcement over workflow instructions

When a constraint matters, enforce it in code — not in agent instructions. A CLI flag that is `required=True` can never be forgotten; a workflow step that says "remember to pass `--jd`" will eventually be skipped. Prefer compilation-level gates (argparse, validation errors, test assertions) over prose rules. If a new guardrail can be a test in `tests/test_consistency.py` or a check in a CLI command, put it there. Reserve CLAUDE.md rules for judgment calls that code cannot express (e.g. selection guardrails).

When changing a schema or data format, migrate **all** existing data files — not just the source copies. Check `applications/*/` for stale formats. A parser that rejects old data it once accepted is a bug if the old data wasn't migrated.

## Architecture (for code changes)

`profile.json` → `profile.py` (slug-keyed loader; the single source of truth for rendering) → `plan.py` (plan parsing/validation) → `selection.py` (Selection model + deterministic trim order) → `renderer.py` (Jake's-template TeX, values verbatim) → `compiler.py` (pdflatex + page count) → `pipeline.py` (orchestration) → `application.py` (1-step apply, lifecycle tracking) → `cli.py`. Off to the side, `db.py` (SQLite/Turso + append-only audit trail) is a *store*, not a source: it imports its types from `profile.py`, is seeded from `profile.json` by `db sync`, and receives application records from `application.py`. Nothing in the render path reads from it. Tests use a small fixture profile, in-memory SQLite, and an injectable fake compiler; they must keep passing without network or pdflatex.
