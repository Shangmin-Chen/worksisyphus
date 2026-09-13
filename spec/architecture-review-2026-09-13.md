# Architecture review — 2026-09-13

HEAD reviewed: [`b654120`](https://github.com/Shangmin-Chen/worksisyphus/commit/b654120) on `review/architecture-slop`.

Six independent reviewers produced the dump in [`_drafts/r3-architecture-slop-findings.md`](_drafts/r3-architecture-slop-findings.md). This document is the filing record: findings grouped into 12 GitHub issues, with closed-issue verification and the habits that keep producing fail-open paths.

The project’s stated contract (CLAUDE.md): fail-closed, deterministic enforcement over workflow instructions, one page, Jake’s template untouched, select-never-write. This pass asked whether the code still does that.

## Already tracked — do not re-file

| Open issue / PR | Named bug |
|---|---|
| [#45](https://github.com/Shangmin-Chen/worksisyphus/issues/45) / [PR #53](https://github.com/Shangmin-Chen/worksisyphus/pull/53) | Trim loop never reports cuts |
| [#46](https://github.com/Shangmin-Chen/worksisyphus/issues/46) / [PR #56](https://github.com/Shangmin-Chen/worksisyphus/pull/56) | Silent data loss in recovery |
| [#47](https://github.com/Shangmin-Chen/worksisyphus/issues/47) / [PR #54](https://github.com/Shangmin-Chen/worksisyphus/pull/54) | Evaluate silent degrade (includes missing-PDF fallback) |
| [#49](https://github.com/Shangmin-Chen/worksisyphus/issues/49) / [PR #55](https://github.com/Shangmin-Chen/worksisyphus/pull/55) | Contact-only DB cross-check |
| [#50](https://github.com/Shangmin-Chen/worksisyphus/issues/50) / [PR #52](https://github.com/Shangmin-Chen/worksisyphus/pull/52) | Non-atomic `export_profile_json` |
| [PR #57](https://github.com/Shangmin-Chen/worksisyphus/pull/57) | pdflatex stderr/timeout + punctuated `G.P.A.` |
| [PR #58](https://github.com/Shangmin-Chen/worksisyphus/pull/58) | Hiring-agent honest upstream status (refuses to change scoring) |
| [PR #59](https://github.com/Shangmin-Chen/worksisyphus/pull/59) | Double-stdin |
| [PR #60](https://github.com/Shangmin-Chen/worksisyphus/pull/60) | Optimizer role-title on `is_engineering` / `is_frontend_web` only |
| [PR #62](https://github.com/Shangmin-Chen/worksisyphus/pull/62) | `meta.json` error contract + folder name cap |
| [PR #63](https://github.com/Shangmin-Chen/worksisyphus/pull/63) | Malformed PDF fail-closed |
| [PR #64](https://github.com/Shangmin-Chen/worksisyphus/pull/64) | Profile loader names bad entry + fixture realign |

## Issues opened this pass

Severity is the reviewers’ rating of the finding that headlines the issue.

### 1. Overflow gate is fail-open — [#65](https://github.com/Shangmin-Chen/worksisyphus/issues/65)

**High.** F-RENDER-1.

`compile_tex` reports overfull hboxes as serialized strings. `tailor()` re-parses those strings and drops any entry it cannot match, treating it as clean. Unmatched overfull is a delivered resume.

Dual source of truth via a stringly-typed API; filter that defaults to pass. Open [PR #57](https://github.com/Shangmin-Chen/worksisyphus/pull/57) would skip malformed widths and widen this hole.

Evidence: `compiler.py:80-81`, `pipeline.py:69-77`, `tests/test_compiler.py:9-26`.

### 2. `compile_tex` publishes before anyone has decided it is deliverable — [#66](https://github.com/Shangmin-Chen/worksisyphus/issues/66)

**High.** F-RENDER-2. Folded: F-RENDER-8 (`tailor(..., plan_name=...)` is dead; CLI tests treat it as load-bearing).

The compiler copies `Simon_Chen_Resume.pdf` into `pdf_dir` as soon as pdflatex writes a file. Page-count and overflow run later in `tailor()`. A failed preview leaves an employer-named PDF on disk.

Distinct from closed [#27](https://github.com/Shangmin-Chen/worksisyphus/issues/27) / [#39](https://github.com/Shangmin-Chen/worksisyphus/issues/39): apply staging still holds. Remaining hole is `tailor` / `compile_tex`. Measurement that publishes; invariant living in the orchestrator instead of the choke point.

Evidence: `compiler.py:61-84`, `pipeline.py:48, 61-62, 67-81`, `tests/test_cli.py:324-332`.

### 3. Seed still deletes ghost application rows — [#67](https://github.com/Shangmin-Chen/worksisyphus/issues/67)

**High.** F-DB-1. **Reopens closed [#30](https://github.com/Shangmin-Chen/worksisyphus/issues/30).**

`seed_database` deletes every applications-table row whose gitignored folder is missing, so a consistency test stays green. Sync can then push the truncation to Turso. A consistency test became the source of truth, so seed was taught to destroy the store.

Evidence: `db.py:475, 494-511, 533-538`, `tests/test_db.py:729-753`.

### 4. Seed overwrites the independent profile copy — [#68](https://github.com/Shangmin-Chen/worksisyphus/issues/68)

**High.** F-DB-2, F-DB-3.

Whenever incoming contact validates, seed `DELETE`s education / experiences / projects / skills and rewrites them from `profile.json`. A thinner file destroys the backup the contact cross-check exists to preserve. Recovery hints were deleted in `afb3dc7`; a dangling comment still names `_DB_CONTACT_RECOVERY_HINT`.

Distinct from open [#49](https://github.com/Shangmin-Chen/worksisyphus/issues/49) (apply comparison scope). Destruction is in seed. Distinct from closed [#33](https://github.com/Shangmin-Chen/worksisyphus/issues/33) (the opposite direction: sync overwriting `profile.json` from the DB — that still holds).

Evidence: `db.py:237-241, 250-260, 257-264, 322-460`.

### 5. Hiring-agent stub scores SWE 97.5 for any resume — [#69](https://github.com/Shangmin-Chen/worksisyphus/issues/69)

**High.** F-EVAL-1.

`evaluate()` is a keyword stub. Empty, Django, systems, and lorem all score 97.5 on the default SWE rubric. `apply()` persists that into `meta.json`. The optimizer ranks plans on it. Tests lock `total_score >= 80`.

Open [PR #58](https://github.com/Shangmin-Chen/worksisyphus/pull/58) names the stub and **refuses to change scoring**. This issue is the scoring lie; #58 is upstream-status honesty. Distinct from open [#47](https://github.com/Shangmin-Chen/worksisyphus/issues/47).

Evidence: `hiring_agent.py:292-355`, `application.py:388-414`, `optimizer.py:64-75, 363-364`, `tests/test_hiring_agent.py:81`.

### 6. Plan-less `apply --role` is a folder title that also picks the rubric — [#70](https://github.com/Shangmin-Chen/worksisyphus/issues/70)

**High.** F-CLI-1. Folded: F-CLI-5 (docs say “combinatorially”; code is three greedy packs), F-CLI-8 (`optimize` does not refuse empty JD text; `apply` does).

One flag, two contracts. `--role` names the application folder and selects the optimizer rubric (default `software_engineer`). Ranking then ignores the JD: `HackerRankHiringAgent.evaluate()` never reads `jd_text`.

Distinct from closed [#31](https://github.com/Shangmin-Chen/worksisyphus/issues/31) (disk overwrite of curated rubrics — HOLDS) and from open [PR #60](https://github.com/Shangmin-Chen/worksisyphus/pull/60) (two guardrail booleans).

Evidence: `cli.py:88-90, 198-200`, `optimizer.py:348, 363`, `hiring_agent.py:284-298, 377-379`.

### 7. Knapsack always keeps every experience; trim cannot cut skills or education — [#71](https://github.com/Shangmin-Chen/worksisyphus/issues/71)

**High / medium.** F-CLI-2, F-RENDER-4, F-CLI-3.

The “knapsack” takes every job, in `profile.json` order, and can exceed its own line budget before packing. Trim then cuts the last job in the file, not the least relevant. `trim_step` only knows projects and experience bullets; skills default to ALL; education is not in `Selection`. Token `web` still admits `personal-website` on backend JDs (`web services` / `web API`).

Distinct from [#45](https://github.com/Shangmin-Chen/worksisyphus/issues/45) (reporting vs what can be cut). Distinct from closed [#37](https://github.com/Shangmin-Chen/worksisyphus/issues/37) (gates exist). [PR #60](https://github.com/Shangmin-Chen/worksisyphus/pull/60) widens the personal-website gate via role title; it does not remove the `web` token.

Evidence: `optimizer.py:78-100, 126-147, 185-197, 262-273, 302-315`, `selection.py:43-60`, `plan.py:57-59`, `renderer.py:55-56`.

### 8. Renderer fail-open on unknown bullets and skill labels — [#72](https://github.com/Shangmin-Chen/worksisyphus/issues/72)

**Medium.** F-RENDER-3, F-RENDER-5.

`parse_plan` fails loudly on unknown slugs. The renderer then silently drops unknown bullet slugs (`if slug in bullets`) and prints unknown skill groups as raw keys (`.get(group, group)`). Fixture uses ghost group `platforms_and_systems`. [PR #64](https://github.com/Shangmin-Chen/worksisyphus/pull/64) realigns the fixture; the fail-open `.get` is not in that PR.

Defensive `in` checks that hide invariant violations.

Evidence: `renderer.py:10-15, 125-128, 161`, `plan.py:40-52`, `tests/conftest.py:86`.

### 9. Contact cross-check has zero tests — [#73](https://github.com/Shangmin-Chen/worksisyphus/issues/73)

**Medium.** F-APPLY-2.

Every `apply()` test uses a non-default `applications_dir`, so the DB path is `None` and only the skip path runs. Not [#49](https://github.com/Shangmin-Chen/worksisyphus/issues/49) (comparison scope vs test coverage).

Covering a safety check with comments and skip-path tests.

Evidence: `application.py:46-74, 104-177, 263-264`, `tests/test_application.py`.

### 10. GPA remainder: CGPA, concatenation, Python-version false positive — [#74](https://github.com/Shangmin-Chen/worksisyphus/issues/74)

**Medium.** F-EVAL-3 remainder.

Misses `CGPA: 3.8` and `GPA3.9`. False-positives `Python 3.11 / 4 worker processes`. Banned metrics are exact strings. Punctuated `G.P.A.` is [PR #57](https://github.com/Shangmin-Chen/worksisyphus/pull/57) — not this issue.

Evidence: `gates.py:21-30`, `tests/test_gates.py:47-51`.

### 11. ATS merged-date still warning-only; section contract fights the renderer — [#75](https://github.com/Shangmin-Chen/worksisyphus/issues/75)

**Medium.** F-EVAL-4, F-EVAL-5. **Reopens the remainder of closed [#36](https://github.com/Shangmin-Chen/worksisyphus/issues/36).**

#36 half-holds: CLI prints warnings after success; `apply()` never fails delivery; renderer still emits tech+date fusion. ATS also requires `Experience` and `Technical Skills` that the renderer omits for a valid projects-only plan. [PR #63](https://github.com/Shangmin-Chen/worksisyphus/pull/63) is malformed-PDF fail-closed, not this contract.

Evidence: `ats.py:13-15, 77-87`, `cli.py:214-217`, `application.py:313-324`, `renderer.py:55-62`, `plan.py:92-93`.

### 12. Consistency tests skip in CI; declared dependencies are inverted — [#76](https://github.com/Shangmin-Chen/worksisyphus/issues/76)

**Medium.** F-ARCH-1, F-ARCH-2. **Reopens closed [#38](https://github.com/Shangmin-Chen/worksisyphus/issues/38).** Folded: F-CLI-6, F-CLI-7, F-ARCH-3, F-ARCH-4.

After `plans/` was deleted, `tests/test_consistency.py` still skip-if-no-`applications/`. That directory is gitignored, so CI asserts nothing. `jinja2` and `libsql-experimental` are unused at runtime; `pdfminer` is required by `apply` but lives in the dev group. Package `__init__` imports `application` → `ats`.

Also in this issue so we do not spam: command tables omit `evaluate --plan`; unknown `args.command` falls through to `tailor`; README still lists `profile.example.json`; `scripts/ats_check.py` is a weaker parallel gate CLAUDE.md still advertises; store/lifecycle cycles papered over with lazy imports.

Evidence: `tests/test_consistency.py:16-18, 29-31, 55-56, 79-80`, `pyproject.toml:11-28`, `src/worksisyphus/__init__.py:3`, `cli.py:481-489`, `README.md:74`.

## Closed-issue verification

What the reviewers re-checked against HEAD `b654120`. “Holds” means the original close is still true. “Does not hold” produced an issue above.

| Closed | Verdict | Notes |
|---|---|---|
| [#27](https://github.com/Shangmin-Chen/worksisyphus/issues/27) gates-before-publish | **Holds** | Apply staging. Remaining hole is `tailor` / `compile_tex` → [#66](https://github.com/Shangmin-Chen/worksisyphus/issues/66) |
| [#28](https://github.com/Shangmin-Chen/worksisyphus/issues/28) orphan folders | **Holds** | Residual staging-dir leak (F-APPLY-5) does not fake history; not re-filed |
| [#29](https://github.com/Shangmin-Chen/worksisyphus/issues/29) DB fatal / Turso logged | **Holds** | |
| [#30](https://github.com/Shangmin-Chen/worksisyphus/issues/30) db init destroying records | **Does not hold** (ghost rows) | [#67](https://github.com/Shangmin-Chen/worksisyphus/issues/67) |
| [#31](https://github.com/Shangmin-Chen/worksisyphus/issues/31) rubric overwrite | **Holds** | Remaining hole is the dual `--role` contract → [#70](https://github.com/Shangmin-Chen/worksisyphus/issues/70) |
| [#32](https://github.com/Shangmin-Chen/worksisyphus/issues/32) silent profile fallback | **Holds** | README still names `profile.example.json` → folded into [#76](https://github.com/Shangmin-Chen/worksisyphus/issues/76) |
| [#33](https://github.com/Shangmin-Chen/worksisyphus/issues/33) db sync overwrites profile.json | **Holds** | Opposite direction from seed clobbering the DB body → [#68](https://github.com/Shangmin-Chen/worksisyphus/issues/68) |
| [#34](https://github.com/Shangmin-Chen/worksisyphus/issues/34) folder naming | **Holds** | |
| [#35](https://github.com/Shangmin-Chen/worksisyphus/issues/35) ARCHIVE vs APPLY | **Holds** | |
| [#36](https://github.com/Shangmin-Chen/worksisyphus/issues/36) ATS warnings discarded | **Half-holds** | CLI prints; apply does not fail; fusion remains → [#75](https://github.com/Shangmin-Chen/worksisyphus/issues/75) |
| [#37](https://github.com/Shangmin-Chen/worksisyphus/issues/37) optimizer guardrails | **Holds** | Gates exist; remaining holes are distinct → [#70](https://github.com/Shangmin-Chen/worksisyphus/issues/70), [#71](https://github.com/Shangmin-Chen/worksisyphus/issues/71) |
| [#38](https://github.com/Shangmin-Chen/worksisyphus/issues/38) consistency tests skip in CI | **Does not hold** | Skip-if-no-applications came back → [#76](https://github.com/Shangmin-Chen/worksisyphus/issues/76) |
| [#39](https://github.com/Shangmin-Chen/worksisyphus/issues/39) tailor clobbering delivered resume | **Holds** (apply path) | Same remaining hole as #27 → [#66](https://github.com/Shangmin-Chen/worksisyphus/issues/66) |

## Findings not filed as their own issues

| ID | Disposition | Reason |
|---|---|---|
| F-EVAL-2 | Not filed | Remainder of open [#47](https://github.com/Shangmin-Chen/worksisyphus/issues/47) / [PR #54](https://github.com/Shangmin-Chen/worksisyphus/pull/54): diagnostic evaluator awards full gate credit when gates did not run |
| F-APPLY-5 | Not filed | Residual of closed [#28](https://github.com/Shangmin-Chen/worksisyphus/issues/28), which holds. Failed second `mkdtemp` can leak `.staging-*`; it does not fake an application folder or block retry |
| F-RENDER-8 | Folded into [#66](https://github.com/Shangmin-Chen/worksisyphus/issues/66) | Dead `plan_name` on `tailor` |
| F-CLI-5, F-CLI-8 | Folded into [#70](https://github.com/Shangmin-Chen/worksisyphus/issues/70) | Combinatorial marketing name; `optimize` empty-JD |
| F-CLI-3 | Folded into [#71](https://github.com/Shangmin-Chen/worksisyphus/issues/71) | Personal-website `web` token |
| F-CLI-6, F-CLI-7, F-ARCH-3, F-ARCH-4 | Folded into [#76](https://github.com/Shangmin-Chen/worksisyphus/issues/76) | Docs/CLI/packaging honesty; do not spam |

## Habits

Synthesized from the dump. Not issues; they are why the same class of bug keeps closing and reopening.

**Keep seeing**

- Fail-open filters (unmatched overfull, unknown bullets, skill `.get`, ATS warnings after success).
- Stringly-typed APIs that the next layer re-parses (`CompileResult.overfull`).
- Invariants in the orchestrator, not the choke point (`compile_tex` publishes; `tailor` decides).
- Skip-path tests for safety checks (contact cross-check; consistency tests without `applications/`).
- Consistency tests that destroy the store to stay green (ghost-row deletion).
- One flag, two contracts (`apply --role`).
- Marketing names in command tables (“combinatorially”, `evaluate --plan` missing from the lists).
- Tests that lock stub scores (`total_score >= 80`).
- Cleanup PRs that delete recovery copy (`_DB_CONTACT_RECOVERY_HINT`).

**Still true, and worth not breaking**

- The render DAG does not import `db`.
- Contact is validated at `render_resume`.
- `apply` stages before publish (#27 holds).
- `--jd` is `required=True`.
- Selection guardrails live in `optimizer.py` (#37 holds as “gates exist”).
- Git-guard fail-closed on missing `origin/main`.
