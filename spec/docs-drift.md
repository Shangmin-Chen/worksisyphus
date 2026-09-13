# Docs drift, merge disagreements, unmerged work

Git wins. Remainder pile: live docs that lag HEAD, pass-1 vs pass-2 disagreements this merge resolved, questions git did not settle, and branches that are **not** shipped.

This file is the spec’s errata: live docs that lag HEAD, merge disagreements resolved against git, and branches that are **not** shipped.

## CLAUDE.md / README / CLI help vs HEAD code

**Placeholder export check is documented, not implemented.** `validate_contact` at `afb3dc7` only requires non-empty `name` / `email` / `phone`. A database or `profile.json` whose contact is `simon@example.com` + `555-555-5555` exports and renders if those strings are non-empty.

- `CLAUDE.md` still says `db export-profile` “refuses to write a placeholder contact block, --force or not.”
- `cli.py` `--force` help: “Does not bypass the placeholder check: a database holding scrubbed contact details is never exported.” Comments around the export CLI repeat that.
- `application.py` comments still talk about detecting placeholder data in the DB, then call the weakened validator.

Those strings are leftover from `e00b1e3`/`652ff4f` and were not updated when `afb3dc7` removed the blocklist. PR #48’s title (“missing or placeholder profile”) also overstates what merged. **GEMINI.md does not repeat the placeholder-export sentence** (CLAUDE-only drift on that line). GEMINI.md *does* mirror the single-stdin sentence.

**`profile.example.json` is in README layout, not in the tree.** Added `8e89415` (rename of tracked `profile.json`), deleted `6640a8b`. README “Layout” still lists `profile.json` (gitignored) and **deleted** `profile.example.json`. There is no committed schema template at HEAD; `tests/fixtures/profile.json` is the test double.

**Single-stdin rule is prose-only.** CLAUDE.md, GEMINI.md, and README: only one of `--jd`/`--plan` may be `-`. HEAD `cli.py` `_read_plan` reads `sys.stdin` independently for each `-`. No argparse mutex, no post-parse check. Both `-` → second read is empty. Unmerged `fix/cli-single-stdin-guard` is not in HEAD. When JD is stdin, pass the plan by path.

**Trim-loop reporting is promised, not recorded.** CLAUDE.md / README tell the agent to report “exactly what the trim loop cut” / “anything the trim loop cut.” Unmerged `fix/45-trim-loop-reports` (`741b9a1` on that branch; current tip `ae4837d`) would write cuts into logs/`meta.json`. At HEAD `pipeline.py` logs `"{n} pages; trimming and recompiling..."` without naming the cut. Infer from plan vs compiled page, or omit the detail.

**Selection guardrails in CLAUDE.md vs optimizer.** CLAUDE.md implies the gates always apply. Code applies `apply_selection_guardrails()` only on the plan-less optimizer path (`6640a8b`). A hand-written `--plan` can include `personal-website` on a quant JD and `apply` will compile it if gates/ATS otherwise pass.

**“Never send canonical” is not mechanical.** `compile` / `compile.sh` still produce `Simon_Chen_Resume_Compiled.pdf`. No command refuses to email it.

**`load_profile` vs “fail-closed contact at load.”** Missing file raises (`e74bcee`). Empty contact is checked at render/apply/seed/export, not inside `load_profile`.

**CLI help vs CLAUDE.md command table** are otherwise close at HEAD (`apply`, `tailor` preview, `db export-profile`, git-gate flags). Present in `cli.py` but missing from CLAUDE.md’s command block and/or README “Manual usage”:

- `db init` (exists; behavior ≈ `db sync` — both `seed_database` then `sync_to_turso`)
- `evaluate --plan <file|-> --jd <file|->`
- `db history --type` (docs only mention `--limit`)
- `status --company` is in README intro prose; CLAUDE’s table lists `status` with no filter flag
- `--url` on apply is in CLAUDE.md, omitted from the README one-liner’s flag list

**Meta-policy vs leftovers.** CLAUDE.md “Deterministic enforcement over workflow instructions” (`1e0c6f4`) still has two undocumented exceptions: single-stdin and placeholder-export wording — still prose, not argparse/blocklist.

**CI gap.** After `edeb27c` / `4320d04`, CI does not ATS-check a tracked employer PDF (there is none). Gate tests use fakes/fixtures; pdflatex is local.

## Merge-time disagreements (pass 1 vs pass 2 vs git)

| Claim | Pass 1 | Pass 2 | Git / this merge |
|-------|--------|--------|------------------|
| GPA value at `2c8149a` | `3.53/4.0` (full-time); internship `3.53` | `3.58` | **3.53** on the tex variants. **3.58** appears later in `06e3587:profile.json`. Pass 2 collapsed two moments. |
| `b2224a7` policy | Select-don't-write: reorder only; do not change facts | “Gemini/AI writes LaTeX” | Prompt forbids changing facts/structure/bullet wording. Title is “Technical Recruiter AI”; it **reorders**. `generate.py` (`018f680`) is the generation era. |
| `resumes_latex/` birth | `17b1e90` (12 role variants + master) | `de15db6` as the folder milestone | Folder **born `17b1e90`**. `de15db6` consolidates to backend/fullstack/mobile/master. |
| `c42e91a` clock | “18:08” | (not timed) | Author **21:08:34 -0400**. |
| `apply` / `archive` coexist | Same-day; archive deleted `a84b998` | “~5 min”; 17:35/17:40 **-0700** | **Confirmed ~5 min.** Git iso-local: `3df5a44` **20:35:24 -0400**, `a84b998` **20:40:44 -0400** (same instant as -0700). |
| `fix/45-trim-loop-reports` tip | `ae4837d` | README said `741b9a1`; docs-drift said `ae4837d` containing `741b9a1` | **Tip `ae4837d`.** `741b9a1` is on the branch, **not** an ancestor of HEAD. |
| `fix/gates-punctuated-gpa-and-compiler-errors` tip | `f1f65c2` (`d02974d` ancestor) | `43db0fb` | **Current tip `43db0fb`.** `f1f65c2` and `d02974d` are ancestors. |
| `review/architecture-slop` | `b654120` (same as HEAD) | (not emphasized) | **Now `ae02d21`** (`docs(spec): record Pass 1b late-reviewer delta…`). Worktree `…/review-architecture`. |
| `master_resume.tex` lines at `d78f844` | 213 (draft A had 214) | (no count) | **213.** Prompt file 0 bytes. |
| Genesis first-parent through `11fe095` | **29** inclusive | (not counted) | **29.** `git rev-list --count --first-parent 56767dc..11fe095` = 28, + start commit. |
| Hardening first-parent vs DAG | 3 merges / 21 DAG | (timeline only) | First-parent `11a6ac2`..HEAD: **3** (`5bf891e`, `3f23740`, `b654120`). Full DAG after `11a6ac2`: **21**. |
| Productization `11fe095..11a6ac2` | 64 | (not counted) | **64 DAG / 37 first-parent.** |
| HEAD tracked files / tests | (not counted) | 73 files; 16 `test_*.py` | **73** / **16**. Draft D’s “18 test_*.py” was 18 directory entries (16 tests + conftest + fixtures). |
| `e57ff6a` file count / lines | ~7875 lines added | 46 files | **46** files, **7875** added / 762 deleted. |
| `0af3a16` date | 2026-07-01 | Draft E had 2026-07-06; pass 2 corrected | **2026-07-01.** |
| `c0abbcc` date / era | nested Aug 18 | Draft E had 2026-08-19 in “Era 4” | **2026-08-18**; first-parent before apply. |
| `GEMINI.md` birth | nested `64c0830` | `--follow` falsely reports `06e3587` | Add-commit **`64c0830`**. |
| `.gitignore` profile/apps | `8e89415` | `8e89415` unanchored; **`dfa1022` anchors** `/profile.json` `/applications/` | Both true; use the two-commit sequence. |
| Four employer resumes with `simon@example.com` | Kept; folders unnamed | Kept; folders unnamed | **Kept.** `e74bcee` body. Do not invent names. |
| Backfill of **47** applications | Kept | (timeline mentions backfill, not 47) | **Kept.** `f2165f3` body. |
| Pre-`371cbe5` folders omitting `contact_verification` | “not recorded” | Draft F “~50”; pass 2 dropped the number | **Omit the number.** `applications/` is gitignored at HEAD; count not verifiable. Absence still means “not recorded.” |
| Fixture fallback “reintroduced” after `e74bcee` | chronology `dfa1022` → `85c6d1b` → close | Pass 2 rejected the reintroduction trap | **Fallbacks predate the fail-closed fix.** Not re-added after it. |
| PDF KB sizes on Persephone restore | Draft A ~117KB→~109KB; pass 1 rejected | (not claimed) | **Not in** `23e5426` / `817734e`. Restore matches `191194d:job hunt/src/Simon_Chen_Resume.tex` (eight-bullet Persephone). |

## Draft disagreements git settled (still true)

Carried from pass 1’s draft-A/B/C checks; git still agrees.

- “7 new” Jul-18/26 folders at `11fe095` while listing eight names → **12** folders total; **8** new on `11fe095`.
- `profile.example.json` still present at productization era end vs “removed from merge” → **deleted** `6640a8b`.

## Questions git did not settle (no rationale in messages)

- Why the aggregator repo absorbed the resume shop (`191194d`) rather than the reverse. Message only cites `0af3a16`.
- Why GPA was added (`2c8149a`, 3.53) then still present as 3.58 in `06e3587` then removed (`6b52555`). CLAUDE.md records Simon’s preference, not the trigger.
- Why `generate.py` (generation) was replaced by `planner.py` (selection) without a decision commit; `06e3587` then removed Gemini entirely.
- Whether intermediate JSON migrations silently changed Persephone/Hermes metrics; only a full diff answers that.
- Why ACLU templates were deleted (`c8b2e27`) with no replacement civic/CRM workflow.
- Whether `afb3dc7` blocklist removal is intentional long-term. No replacement detector on `main`. CLAUDE.md/CLI still describe the old check.
- Bosch without `plan.json`: documented in `jd.txt` (`18fda15`), not machine-enforced. Unrecoverable from `plans/` after `c3e22a0` except via git history.
- Collaborator story after `8e89415`: historical applications live in git ancestry; fresh clones need Turso or a local copy. Not spelled out beyond gitignore.

## Unmerged `fix/*` — not in HEAD

Do not describe as shipped. Tips from `git log -1` on this worktree (2026-09-13). None of these are ancestors of `b654120`.

| Branch | Tip | Worktree (if any) | Focus |
|--------|-----|-------------------|--------|
| `fix/45-trim-loop-reports` | `ae4837d` | `…/issue-45` | Record trim-loop cuts in logs + `meta.json` (contains `741b9a1`) |
| `fix/46-db-silent-data-loss` | `1903420` | `…/issue-46` | Fail closed on seed skips / fake Turso success / corrupt meta |
| `fix/47-evaluate-silent-degrade` | `adc9938` | `…/issue-47` | Refuse empty PDFs; no silent evaluate fallback |
| `fix/49-profile-db-drift` | `69315a3` | `…/issue-49` | Warn on non-contact profile drift vs DB |
| `fix/50-atomic-export-profile` | `4365893` | `…/issue-50` | Atomic tmp+replace for `export_profile_json` |
| `fix/application-meta-error-contract` | `4642dc7` | (none extra) | Validate allocated folder name length after suffix |
| `fix/ats-malformed-pdf-fail-closed` | `5905dc0` | | Mypy / ATS PDF extraction |
| `fix/cli-single-stdin-guard` | `613ff68` | | Intended argparse single-stdin + test/mypy |
| `fix/db-refuse-corrupt-application-meta` | `9096eb3` | | Corrupt `meta.json` refusal |
| `fix/gates-punctuated-gpa-and-compiler-errors` | `43db0fb` | | Tighter GPA patterns (`d02974d` / `f1f65c2` are ancestors) |
| `fix/hiring-agent-cycle2-upstream-exits` | `ab29bb3` | | Upstream check on untracked/empty SHA |
| `fix/hiring-agent-honest-upstream-status` | `0f17e2a` | | Honest hiring-agent sync status |
| `fix/optimizer-role-title-guardrails` | `0fac660` | | Suppress mobile JD keywords under engineering role |
| `fix/profile-loader-names-bad-entry` | `d5c7d7f` | | Coursework validation in profile loader |
| `review/architecture-slop` | `ae02d21` | `…/review-architecture` | Spec review notes; **not** HEAD behavior |

Issue-numbered branches (`45`–`50`) have extra worktrees. Local-only `fix/*` without issue numbers also exist and are equally unmerged. `main` at `/Users/shangminchen/worksisyphus` is `b654120`. This worktree is `docs/spec-timeline` at `b654120`.

## Live docs vs history (not bugs, but easy to misread)

CLAUDE.md architecture paragraph still says nothing on the render path reads SQLite — accurate for bullets/TeX, but omits that **`apply` reads the contact row for cross-check** (`371cbe5`), now documented in `architecture.md`. Treat the spec module map as the fuller contract.

GEMINI.md tracks CLAUDE.md from `64c0830` and was synced again in `ae9312c` (#25) plus later apply/plans-removal docs commits. Treat CLAUDE.md as canonical if they ever diverge; this merge did not line-diff them beyond the placeholder-export / single-stdin sentences.

README workflow bullets mention `App#`, `_N` suffixes, and the git gate — those are accurate at HEAD (`e4f4cd2`, `e92de45`). README still lists `profile.example.json` in the layout tree, which is not accurate.

`scripts/ats_check.py` remains as a manual/CI helper; delivery ATS runs through `ats.py` inside `apply`. Using the script on `applications/<app>/Simon_Chen_Resume.pdf` is still valid and documented.

Bosch (`2026-07-09_bosch_software_engineer_ii`) remains the documented archive without `plan.json`. After `8e89415` it is not in a fresh clone’s git tree at HEAD (applications gitignored); the annotation lives in commit `18fda15`. Agents on a machine with local `applications/` should not “repair” it.

## Audit round 1 dispositions

Independent audit against git at HEAD `b654120`. Git verified each finding before edit.

**Accepted (applied):**

1. **P0** — `apply` reads SQLite for contact cross-check (`371cbe5`); split render-path vs apply-path in `architecture.md` and `invariants.md`.
2. **P1** — `11fe095` one-time archive regeneration (hyphen URL, Bosch/Fomo exceptions, immutability note).
3. **P1** — `a0e025d` Shangmin → Simon display name.
4. **P1** — `63b89ff` intern track birth; `587f79f` internship-variant death (not lasting until `0af3a16`).
5. **P1** — `cf5f217` / `5a91167` master-tex drops vs `0af3a16` JSON resurrection; real purge `06e3587`.
6. **P1** — `6640a8b` fixture PII scrub + causal link to placeholder incident (no live PII quoted).
7. **P1** — `evaluate --check-upstream` fail-open; `roles/upstream_manifest.json` live; `.provenance.json` dead.
8. **P2** — `tex_files/` born `8c83568`; `__main__.py` at `f3ca492`; `17b1e90` renames not deletes master/tailored pair.
9. **P2** — Canonical has no page limit; delivery overflow fail is >2pt not any overfull.
10. **P2** — `.env.example`, `upstream_manifest.json` in HEAD snapshot; `db init|sync` flags (no `--no-sync`); backfill seed fail-closed.
11. **P2** — Productization 64 DAG / 37 first-parent; density floors; `f2165f3` in-memory role rubrics.
12. **P2/P3** — `da81003` LinkedIn `www.`; `c3e22a0` 46 plan JSONs; `f3ca492` compile.sh unchanged; four aggregator console scripts; CI `ruff format --check`.

**Skipped (auditor confirmed or no change needed):**

- Uncited first-parent commits (`3468414`, `b78c76d`, etc.) — audit agrees they are not load-bearing; not added to timeline.
- Pass-1/2 merge disagreements already resolved in prior merge — only productization count updated here.
- All findings git-checked; none rejected as false.

## Audit round 2 dispositions

Second independent audit against git at HEAD `b654120`. Round-1 fixes confirmed; no new P0/P1. Git verified each new finding before edit.

**Applied (P2 + cheap P3):**

1. **P2 #1** — Architecture ASCII: contact cross-check before renderer/compiler (matches `application.apply` lines 260–264). `contact_verification` always frozen, including on skip.
2. **P2 #2** — Timeline: `85c6d1b` (18:09) before ancestor `6640a8b` (22:47); incident chronology includes scrub step.
3. **P2 #3** — Apply fail-open when `worksisyphus.db` absent (folder publishes, no insert/Turso/cross-check, exit 0); Turso skip reasons warn only. Pointed at unmerged `fix/46-db-silent-data-loss`.
4. **P2 #4** — `--check-upstream` always exit 0; statuses `synced`/`outdated`/`untracked`/`rate_limited`/`cached`; corrupt local manifest is exit 1, not fail-open.
5. **P2 #5** — Test-only fixture fallback in `conftest.real_profile`; production `load_profile` does not.
6. **P2 #6** — Six-field contact mismatch; skip still writes `contact_verification`.
7. **P2 #7** — Omitted `--role` → folder stem `swe` vs rubric `software_engineer`.
8. **P3 #8** — HEAD tree ASCII adds `.gitignore`, `.github/workflows/ci.yml`.
9. **P3 #9** — Module-births `db` parenthetical qualified (store; apply reads contact only).

**Skipped (auditor agreed or not LLM-trap):**

- Residual uncited commits (`5282ac3`, TUI micro-commits, `2c63d16` except as support for #5) — not load-bearing; not added.
- CLAUDE.md vs spec drift items already catalogued above — no spec regression.
- Unmerged `fix/*` behavior — listed, not described as shipped (except where noted as would-change).
