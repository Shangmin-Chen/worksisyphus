# spec/ — worksisyphus history (canonical)

LLM-facing history of how the resume compiler reached **HEAD `b654120`**. This folder is **why** the live rules exist and which workflows later died. It is **not** the runbook.

**Live operator docs are `CLAUDE.md` at repo root** (mirrored by `GEMINI.md`). Follow those for apply / `--jd` / scratch plans. Use this folder only to avoid resurrecting deleted paths (`plans/`, `resumes/`, `archive`, Gemini, TUI, fixture fallback, placeholder-string blocklist) and to see which CLAUDE.md sentences are still prose-only.

Synthesized from two independent git-history passes (chronological eras, then paths/CLI/policy), merged, then audited against `git log` / `git show` at HEAD. Git wins over draft claims.

## Read order

1. `README.md` (this file) — topology, counts, caveats
2. `timeline.md` — chronological milestones (~42, not all 134 commits)
3. `invariants.md` — current-as-of-HEAD rules with landing hashes
4. `architecture.md` — modules, directory snapshots, deleted paths, LLM traps
5. `agent-workflow.md` — era workflows **and** HEAD command registry (live + dead)
6. `docs-drift.md` — docs vs code vs history; merge-time disagreements; unmerged `fix/*`

## HEAD

| Fact | Value |
|------|--------|
| HEAD | `b654120` (2026-09-13) — Merge pull request #51 (`feat/db-git-freshness-gate`) |
| Full DAG | **134** commits (includes the LaTeX-shop second-parent line) |
| First-parent | **69** commits (Python-root integration history) |
| Tracked files | **73** (`git ls-tree -r --name-only HEAD`) |
| Tests | **16** `tests/test_*.py` + `conftest.py` + `tests/fixtures/profile.json` |
| This branch | `docs/spec-timeline` at the same commit as `main` |

## Git topology caveat (two roots)

Two true roots exist (`git merge-base` empty). **First-parent from HEAD is not the resume-content line.**

| Root | Hash | Date | What it was |
|------|------|------|-------------|
| LaTeX shop | `d78f844` | 2025-09-19 | `master_resume.tex` (213 lines), empty `ai_agent_prompt.txt` (0 bytes), `job_description.txt`, `tailored_resume.tex` |
| Python aggregator | `56767dc` | 2026-07-02 | `worksisyphus-aggregate` / `-normalize` / `-enrich` / `-catalog`; zero resume code |

**First-parent from HEAD:** `56767dc` → `191194d` → `6ed0848` → … → `b654120`. That line answers *when* something landed on main.

**Content archaeology:** `191194d` (2026-07-02) is a subtree merge whose second parent is `0af3a16` (restructured LaTeX shop, author date **2026-07-01**). Walk `0af3a16` → `d78f844` for Jake's template and resume facts. LaTeX-lineage hashes before `191194d` are ancestors of HEAD but **absent** from `git log --first-parent`. The aggregator from `56767dc` is deleted the next pivot (`6ed0848`).

## Unmerged branches are not shipped

`git branch --no-merged HEAD` lists `fix/45-*` … `fix/50-*` plus local `fix/*`. None of that is current behavior. See `docs-drift.md` for current tips and worktrees. Do not describe trim-loop `meta.json` cuts, argparse single-stdin, or atomic export as shipped.

## Conventions

- **Landed** = the commit that introduced the behavior on ancestry that reached HEAD, not necessarily the GitHub merge. Merge hashes are noted when they are the integration point (`6564917` apply, `2a57152` `resumes/`, `11a6ac2` `plans/`, `5bf891e` reapplication, `3f23740` fail-closed profile, `b654120` git gate).
- Dates are author dates (`git log --date=short`). Hashes are 7 hex chars.
- If a pass and git disagree, **git wins**. Survivors are in `docs-drift.md`, not averaged.
- Incidents only when a commit message states them (`e74bcee`, `e00b1e3`, `652ff4f`). Do not invent folder names or extra counts.

## HEAD traps (read before acting)

- No `plans/` or `resumes/` in the tree. `tailor` previews into `tex_files/`; **`apply` delivers**.
- `archive` is gone (`a84b998`). Fixture fallback is gone (`e74bcee` / `652ff4f`).
- Placeholder *string* blocklist is gone (`afb3dc7`) while CLAUDE.md / `--force` help still mention it.
- `--jd` / `--plan` single-stdin is **prose-only**; HEAD `cli.py` does not enforce it.
- Selection guardrails in code run only when `apply` **omits** `--plan`.
- Missing `profile.json` is a hard error. Never load `tests/fixtures/profile.json` for delivery (pre-`6640a8b` fixture commits hold real PII in git history).
- `apply` cross-checks six contact fields against the DB **before compile** when `worksisyphus.db` exists (`371cbe5`); no DB file → folder still publishes, no insert/Turso/cross-check. Do not delete the DB to “unblock,” and do not treat exit 0 as “DB recorded this send.”
- Production never loads `tests/fixtures/profile.json`; `conftest.real_profile` still does, for tests only.
- `evaluate --check-upstream` always exits 0 (`cached`/`outdated`/`untracked` still success); corrupt local manifest is the exception (exit 1).
- Turso sync from this `docs/spec-timeline` branch is skipped unless `--allow-branch` / `--no-git-check` — that is intended.

## How this folder was built

Two independent syntheses (chronological eras vs paths/CLI/policy), then a merge that kept unique facts from both, then an audit loop against git until no remaining P0/P1 gaps. Conflicts and dispositions live in `docs-drift.md`.
