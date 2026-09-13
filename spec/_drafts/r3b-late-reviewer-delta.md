# Late-reviewer delta — do not re-file #45–#76

Second wave (parallel reviewers that finished after #65–#76). HEAD still `b654120`. Worktree: `/Users/shangminchen/worksisyphus-wt/review-architecture`. Branch: `review/architecture-slop`. Update PR #77 spec after filing.

## Already covered — comment on existing issue if useful, do NOT open a new one

- Ghost-row wipe / no Turso pull as the *wipe* mechanism → #67
- Seed overwrites profile body / recovery hints → #68
- Hiring-agent stub 97.5 / optimizer ranks on it / tests lock >=80 / unused jinja → #69
- `--role` dual contract / empty role three identities / format_hackerrank_report reloads without JD → #70
- Knapsack keeps every experience / skills ALL / personal-website `web` token / PR #60 remnant on is_engineering JD-only → #71 (comment with the extra `is_engineering` / trim-guts-persephone evidence if it is the same fix)
- Renderer silent drop unknown bullets / skill `.get` → #72
- Contact cross-check untested / skip path only → #73
- CGPA / GPA3.9 / Python 3.11/4 → #74
- Merged-date warning-only / ATS requires Experience → #75
- Consistency skip in CI / inverted deps / GEMINI drift / ats_check.py / lazy import cycle / else-tailor / evaluate --plan missing from tables → #76
- compile_tex publishes early / dead plan_name → #66
- Overflow fail-open strings → #65
- Contact-only cross-check overclaim / circular ATS vs profile → #49
- Evaluate empty/missing PDF → #47 (including `--hackerrank` scoring empty text)
- Non-atomic export → #50
- Turso swallow False → #46
- Trim does not *report* cuts → #45
- Staging `.staging-*` leak on second mkdtemp → residual of closed #28, previously not filed

## NEW — file these (group tightly, ~6–8 issues max)

### N1 — high — apply publish vs persist are two transactions
Apply `os.replace`s the folder, THEN persist. Missing DB → silent skip-and-succeed. Insert failure → raise AFTER folder exists (`status: applied`); retry allocates `_2`. `get_connection` can create an empty `.db` so later apply publishes then `OperationalError`.
`update_application_status` writes `meta.json` first, then maybe the DB — same split on the only allowed mutation of a published folder.
`_sync_cloud` always dumps `DEFAULT_DB_PATH`, not `resolved_db_path`.
Files: application.py 337–385, 585–610; db.py 148–157, 662–674, 767–773
Distinct from closed #28 (pre-publish leftovers) and #29 (`except: pass`).

### N2 — high — git fetch timeout fail-opens on stale origin/main
#51 fail-closes when `origin/main` is *missing*. Fetch timeout/non-zero is `except: pass`; cached `behind==0` is allowed. `test_git_freshness_handles_fetch_timeout_and_offline` asserts `allowed is True`.
Files: git_guard.py 82–125; tests/test_git_guard.py 112–126
Remaining hole after #51, not #51 itself.

### N3 — high — selection guardrails are optimizer-only; `--plan` is unenforced
`apply_selection_guardrails` only inside `generate_candidate_plans`. `apply --plan` / `validate` / `parse_plan` only check slugs exist. CLAUDE.md claims optimizer enforces them “in code” and also “when a constraint matters, enforce it in code.” Preferred author (agent `--plan`) is the path with no code. Can ship `fitness-tracker` on a systems JD.
Files: optimizer.py 232–287; plan.py 80–99; cli.py 197–201; CLAUDE.md 12–21, 40–42
Distinct from #37 (optimizer path now has gates) and from #71 (what knapsack *selects*).

### N4 — high — `real_profile` still launders the fixture; placeholder contact still renders
Production `load_profile` fails if the file is missing. Tests: `real_profile` falls back to `tests/fixtures/profile.json` (`simon@example.com` / `555-555-5555`). `validate_contact` is non-empty only (`afb3dc7` deleted the blocklist). Fixture contact renders and compiles; ATS compares PDF to the same profile. `load_profile` synthesizes `Contact(name="")` if `contact` key missing.
Files: tests/conftest.py 16–26; profile.py 61–67, 79–81; tests/fixtures/profile.json
Distinct from closed #32 (production fallback). Distinct from #73 (skip-path tests). Product decision in `afb3dc7` removed placeholder refusal — this issue is that the incident class is back at the choke point.

### N5 — medium — export --force can overwrite last profile.json with a hollow DB
Distinct from #50 (atomicity) and #68 (seed direction). Export validates contact only; `test_export_profile_json` inserts only a contact row and exports empty body. `--force` overwrites with no sidecar.
Files: db.py 543–605; cli.py 311–319; tests/test_db.py 213–229

### N6 — medium/high — trim guts the top project before lower-ranked experience bullets
After dropping extra projects, next cuts are bullets on the *last remaining project* (highest-ranked / persephone) down to MIN_BULLETS *before* any experience bullets. Tests lock this in (`test_trim_drops_projects_first_then_bullets`). CLAUDE.md: rank order is relevance; trim cuts from the bottom.
This is a *different bug* from #71’s “knapsack never drops an experience / skills not trimable.” Comment on #71 ONLY if you judge one PR should fix both; otherwise its own issue.
Files: selection.py 43–60; pipeline.py 65–81; tests/test_selection.py

### N7 — medium — policy gates never scan profile.json; tailor/compile skip the battery; density/ATS pass filler
No-GPA / banned-content only run on apply’s extracted PDF. `compile` and `tailor` write recruiter-named/canonical PDFs with no gates. Density is `len(text.split())` — `"word " * 400` passes. `scripts/ats_check.py` default `require_contact=False`.
Gate score 10/10 when evaluator never ran gates (F-EVAL-2) — previously left on #47; this wave says it is the *opposite* of #47 (skipped looks like perfect pass, not empty). If you agree it is distinct, fold it HERE not as a 13th issue. If you still think #47 covers it, `gh issue comment` on #47.
Files: gates.py 50–77, 95–112, 148–157; pipeline.py 32–81; ats.py 56–97; evaluator.py 228–247

### N8 — medium — Turso is last-snapshot-wins; “append-only audit” is local-only; no application restore
Local audit is insert-only. Every Turso sync `DROP TABLE audit_events` and restores this machine’s snapshot. No `db pull`. Combined with #67’s prune this is the restore story. File as the *honesty/restore* issue if it is not just a duplicate of #67’s wipe. If duplicate, comment on #67.
Files: db.py 116–126, 181–204, 738–764; .gitignore; CLAUDE.md

## Do not file
- Staging leak F-APPLY-5 (closed #28 holds)
- Compile.sh alias
- Anything already in open PRs #52–#64 named bug

After filing: update `spec/README.md` and `spec/architecture-review-2026-09-13.md` with a “Pass 1b” section linking new issue numbers. Append a short note to the drafts file pointing at what was filed. Do not commit or push.

---

## Filed (Pass 1b) — 2026-09-13

All eight NEW items filed; none merged. Comments on existing issues instead of new tickets where the delta asked.

| Delta | Issue | URL |
|---|---|---|
| N1 | [#78](https://github.com/Shangmin-Chen/worksisyphus/issues/78) | publish vs persist |
| N2 | [#79](https://github.com/Shangmin-Chen/worksisyphus/issues/79) | fetch timeout fail-open |
| N3 | [#80](https://github.com/Shangmin-Chen/worksisyphus/issues/80) | guardrails optimizer-only |
| N4 | [#81](https://github.com/Shangmin-Chen/worksisyphus/issues/81) | `real_profile` fixture launder |
| N5 | [#82](https://github.com/Shangmin-Chen/worksisyphus/issues/82) | export `--force` hollow DB |
| N6 | [#83](https://github.com/Shangmin-Chen/worksisyphus/issues/83) | trim guts top project — **own issue**, not folded into #71 |
| N7 | [#84](https://github.com/Shangmin-Chen/worksisyphus/issues/84) | gates skip `profile.json`; F-EVAL-2 folded here (opposite of #47) |
| N8 | [#85](https://github.com/Shangmin-Chen/worksisyphus/issues/85) | Turso last-snapshot-wins — **own issue**, not a #67 dupe |

Comments: [#71](https://github.com/Shangmin-Chen/worksisyphus/issues/71#issuecomment-5651892064) (`is_engineering` remnant + #83 split), [#47](https://github.com/Shangmin-Chen/worksisyphus/issues/47#issuecomment-5651892146) (F-EVAL-2 → #84), [#67](https://github.com/Shangmin-Chen/worksisyphus/issues/67#issuecomment-5651892258) (#85 companion), [#50](https://github.com/Shangmin-Chen/worksisyphus/issues/50#issuecomment-5651892346) (#82 ≠ atomicity), [#73](https://github.com/Shangmin-Chen/worksisyphus/issues/73#issuecomment-5651892440) (#81 ≠ skip-path tests).

Not filed: F-APPLY-5 (closed #28), compile.sh alias, already-covered #65–#76 / #45–#50.
