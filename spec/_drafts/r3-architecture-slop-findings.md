# Architecture/slop review findings — HEAD b654120

Review date: 2026-09-13. Worktree: review/architecture-slop.
Six independent Cursor 4.6 reviewers. Do not re-file open issues #45 #46 #47 #49 #50 or the bugs already named by open PRs #52–#64, except when a CLOSED issue was shown not to hold.

## Already tracked (do not open)

- #45 / PR #53 — trim loop never reports cuts
- #46 / PR #56 — silent data loss in recovery
- #47 / PR #54 — evaluate silent degrade (includes F-CLI-4 missing-PDF fallback)
- #49 / PR #55 — contact-only DB cross-check (F-APPLY-1)
- #50 / PR #52 — non-atomic export_profile_json
- PR #57 — pdflatex stderr/timeout + punctuated GPA (F-RENDER-6; G.P.A. half of F-EVAL-3)
- PR #58 — hiring-agent honest upstream status
- PR #59 — double-stdin
- PR #60 — optimizer role-title on is_engineering / is_frontend_web only
- PR #62 — meta.json error contract + folder name cap (F-APPLY-3, F-APPLY-4)
- PR #63 — malformed PDF fail-closed (not the ATS header mismatch)
- PR #64 — profile loader names bad entry + fixture realign (F-RENDER-7 partial)

## Closed-issue verification

- #27 gates-before-publish HOLDS
- #28 orphan folders HOLDS (see residual F-APPLY-5)
- #29 DB fatal / Turso logged HOLDS
- #31 rubric overwrite HOLDS
- #32 silent profile fallback HOLDS
- #33 db sync overwrites profile.json HOLDS
- #34 folder naming HOLDS
- #35 ARCHIVE vs APPLY HOLDS
- #36 ATS warnings discarded HALF-HOLDS (CLI prints; apply does not fail; F-EVAL-4)
- #37 optimizer guardrails HOLDS (gates exist; remaining holes are distinct)
- #38 consistency tests skip in CI DOES NOT HOLD — skip-if-no-applications came back (F-ARCH-1)
- #30 db init destroying records DOES NOT HOLD for ghost-row deletion (F-DB-1)

---

## F-RENDER (core render path)

### F-RENDER-1 — high
Horizontal-overflow gate is fail-open: compiler and pipeline share a stringly-typed format, unmatched overfull is treated as clean.
Files: compiler.py:80-81, pipeline.py:69-77, tests/test_compiler.py:9-26
Habit: dual source of truth via serialized strings; filter that defaults to pass.
Not tracked. PR #57 would skip malformed widths and widen this hole.

### F-RENDER-2 — high
compile_tex publishes the PDF before anyone has decided it is deliverable; failed tailor() leaves Simon_Chen_Resume.pdf on disk.
Files: compiler.py:61-84, pipeline.py:67-81
Habit: measurement that publishes; invariant living in the orchestrator instead of the choke point.
Distinct from closed #27/#39 (apply staging). Remaining hole is tailor/compile_tex.

### F-RENDER-3 — medium
Renderer silently drops unknown bullet slugs (`if slug in bullets`); unknown entry ids crash. Last-mile fail-open.
Files: renderer.py:125-128, 134; plan.py:40-52
Habit: defensive `in` checks that hide invariant violations.

### F-RENDER-4 — medium
Trim only knows projects and experience bullets; skills default to ALL; education is not in Selection. Overflow cannot be fixed by selecting less on headings/coursework/skills.
Files: selection.py:43-60, plan.py:57-59, renderer.py:55-56, pipeline.py:68-75
Distinct from #45 (reporting vs what can be cut).

### F-RENDER-5 — medium
Skill-group display names are a second schema; unknown groups render as raw keys via `.get(group, group)`. Fixture uses ghost group `platforms_and_systems`.
Files: renderer.py:10-15, 161
PR #64 realigns fixture; fail-open `.get` is not in that PR.

### F-RENDER-8 — low
`tailor(..., plan_name=...)` is dead; CLI tests treat it as load-bearing.
Files: pipeline.py:48, 61-62; tests/test_cli.py:324-332

## F-APPLY (application lifecycle)

### F-APPLY-2 — medium
Contact cross-check has zero tests; every apply() test exercises only the skip path.
Files: application.py:46-74, 104-177, 263-264
Habit: covering a safety check with comments and skip-path tests.
Not #49 (scope of comparison vs test coverage).

### F-APPLY-5 — low
Staging dir created outside cleanup try; failed second mkdtemp leaks `.staging-*`. Does not reopen #28.
Files: application.py:282-355

## F-DB (store + git_guard)

### F-DB-1 — high
Ghost-row deletion reopens closed #30: missing gitignored folders shrink the applications table, then Turso can push the truncation.
Files: db.py:475, 494-511, 533-538; tests/test_db.py:729-753
Habit: a consistency test became the source of truth, so seed was taught to destroy the store.

### F-DB-2 — high
seed_database overwrites the independent profile copy whenever contact is valid — a thinner profile.json destroys the backup the cross-check exists to preserve.
Files: db.py:257-264, 322-460
Distinct from #49: destruction is in seed, not apply. Once seed has run there is nothing left to warn about.

### F-DB-3 — medium
Load-bearing recovery hints deleted in afb3dc7; refusal no longer forbids re-running db sync; dangling comment names missing constant `_DB_CONTACT_RECOVERY_HINT`.
Files: db.py:237-241, 250-260

## F-CLI (CLI + optimizer)

### F-CLI-1 — high
Plan-less `apply --role` is a folder title that also picks the optimizer rubric; ranking then ignores the JD. Default software_engineer. HackerRankHiringAgent.evaluate() never reads jd_text.
Files: cli.py:88-90,198-200; optimizer.py:348,363; hiring_agent.py:284-298,377-379
Distinct from #31 (disk overwrite) and PR #60 (two guardrail booleans).

### F-CLI-2 — high
The “knapsack” always takes every experience, in profile.json order, and can exceed its own line budget before packing. Trim then cuts the last job in the file, not the least relevant.
Files: optimizer.py:78-100,126-147,302-315; selection.py:43-60

### F-CLI-3 — medium
Token `web` still admits `personal-website` on backend JDs (`web services` / `web API`).
Files: optimizer.py:185-197,262-273
PR #60 widens this gate via role title.

### F-CLI-5 — medium
Docs say combinatorially find highest-scoring plan; code is three greedy packs. Skills always all.

### F-CLI-6 — low-medium
Command tables omit implemented `evaluate --plan`. Three hand-maintained lists, no argparse↔docs test.

### F-CLI-7 — low
Unknown/future subcommands fall through to `tailor` (else branch).

### F-CLI-8 — low-medium
`optimize` does not refuse empty JD text; `apply` does.

## F-EVAL (gates + ATS + hiring-agent)

### F-EVAL-1 — high
Hiring-agent evaluate() is a stub; SWE score invariant at 97.5 for empty, Django, systems, and lorem. apply() persists this into meta.json; optimizer ranks on it. Tests lock `total_score >= 80`.
Files: hiring_agent.py:292-355; application.py:388-414; optimizer.py:64-75,363-364
PR #58 names the stub and refuses to change scoring. Distinct from #47.

### F-EVAL-2 — medium
Diagnostic evaluator awards full gate credit (10/10) when it did not run gates. evaluate_resume_text("", "") overall 45.
Distinct remainder of #47 (no PDF → pretend gates passed).

### F-EVAL-3 remainder — medium
GPA gate misses `CGPA: 3.8` and `GPA3.9`; false-positives `Python 3.11 / 4 worker processes`. Banned metrics are exact strings.
Punctuated G.P.A. is PR #57.

### F-EVAL-4 — medium
Merged tech+date still cannot fail delivery. #36 only half-fixed: warnings print on CLI after success; apply() never logs them; renderer still emits fusion.
#36 closed. Remaining hole untracked.

### F-EVAL-5 — medium
ATS requires Experience (and Technical Skills) that the renderer will omit for a valid projects-only plan.
Bundled inside PR #63 as extra, not the named malformed-PDF bug — still file if synthesizer judges it distinct enough.

## F-ARCH (cross-cutting)

### F-ARCH-1 — medium
tests/test_consistency.py still asserts nothing in CI (all four skip without gitignored applications/). #38 close was overtaken when plans/ was deleted.

### F-ARCH-2 — medium
Declared dependencies inverted: jinja2 and libsql-experimental unused at runtime; pdfminer required by apply lives in the dev group. Package __init__ imports application → ats.

### F-ARCH-3 — low
Store/lifecycle cycle papered over with lazy imports. Identifier grammar belongs in a leaf module.

### F-ARCH-4 — low
README still lists profile.example.json; scripts/ats_check.py is a weaker parallel gate that CLAUDE.md still advertises.

## Habits (synthesize, do not file as issues)

Fail-open filters; stringly-typed APIs; invariants in the orchestrator not the choke point; skip-path tests for safety checks; consistency tests that destroy the store to stay green; one flag two contracts; marketing names in agent command tables; tests that lock stub scores; cleanup PRs that delete recovery copy.
Good: render DAG does not import db; contact at render_resume; apply staging; --jd required=True; guardrails in optimizer.py; git-guard fail-closed on missing origin/main.
