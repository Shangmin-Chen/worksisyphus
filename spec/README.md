# Architecture review specs

This directory is the public record of the 2026-09-13 architecture/slop review of worksisyphus.

The project’s contract is fail-closed and mechanically enforced: one page, Jake’s template untouched, select-never-write, quality gates before a resume is considered delivered. This pass asked whether the code still does that at HEAD `b654120` (`review/architecture-slop`).

## How to read

1. **[architecture-review-2026-09-13.md](architecture-review-2026-09-13.md)** — grouped findings, each group linked to the GitHub issue opened from it, plus the habits this pass kept seeing and a closed-issue verification table. Pass 1 is issues [#65](https://github.com/Shangmin-Chen/worksisyphus/issues/65)–[#76](https://github.com/Shangmin-Chen/worksisyphus/issues/76); Pass 1b is [#78](https://github.com/Shangmin-Chen/worksisyphus/issues/78)–[#85](https://github.com/Shangmin-Chen/worksisyphus/issues/85).
2. **[_drafts/r3-architecture-slop-findings.md](_drafts/r3-architecture-slop-findings.md)** — raw, de-duped reviewer dump. Kept as the source notes. Not the filing record; do not treat IDs like `F-RENDER-1` as issues.
3. **[_drafts/r3b-late-reviewer-delta.md](_drafts/r3b-late-reviewer-delta.md)** — Pass 1b assignment: NEW vs already-filed. Kept as the source notes for [#78](https://github.com/Shangmin-Chen/worksisyphus/issues/78)–[#85](https://github.com/Shangmin-Chen/worksisyphus/issues/85).

Do not re-file open [#45](https://github.com/Shangmin-Chen/worksisyphus/issues/45) [#46](https://github.com/Shangmin-Chen/worksisyphus/issues/46) [#47](https://github.com/Shangmin-Chen/worksisyphus/issues/47) [#49](https://github.com/Shangmin-Chen/worksisyphus/issues/49) [#50](https://github.com/Shangmin-Chen/worksisyphus/issues/50) [#65](https://github.com/Shangmin-Chen/worksisyphus/issues/65)–[#76](https://github.com/Shangmin-Chen/worksisyphus/issues/76) or the named bugs of open PRs [#52](https://github.com/Shangmin-Chen/worksisyphus/pull/52)–[#64](https://github.com/Shangmin-Chen/worksisyphus/pull/64).

## Issues opened this pass (Pass 1)

| # | Title |
|---|-------|
| [65](https://github.com/Shangmin-Chen/worksisyphus/issues/65) | Overflow gate is fail-open |
| [66](https://github.com/Shangmin-Chen/worksisyphus/issues/66) | `compile_tex` publishes before deliverable |
| [67](https://github.com/Shangmin-Chen/worksisyphus/issues/67) | Seed deletes ghost application rows — reopens #30 |
| [68](https://github.com/Shangmin-Chen/worksisyphus/issues/68) | Seed overwrites the independent profile copy |
| [69](https://github.com/Shangmin-Chen/worksisyphus/issues/69) | Hiring-agent stub score 97.5 used as real |
| [70](https://github.com/Shangmin-Chen/worksisyphus/issues/70) | Plan-less `apply --role` dual contract |
| [71](https://github.com/Shangmin-Chen/worksisyphus/issues/71) | Knapsack keeps every job; trim cannot select less |
| [72](https://github.com/Shangmin-Chen/worksisyphus/issues/72) | Renderer fail-open on unknown bullets/labels |
| [73](https://github.com/Shangmin-Chen/worksisyphus/issues/73) | Contact cross-check has zero tests |
| [74](https://github.com/Shangmin-Chen/worksisyphus/issues/74) | GPA remainder (CGPA / concat / false-positive) |
| [75](https://github.com/Shangmin-Chen/worksisyphus/issues/75) | ATS merged-date still warning-only — reopens #36 remainder |
| [76](https://github.com/Shangmin-Chen/worksisyphus/issues/76) | Consistency tests skip in CI — reopens #38 |

## Issues opened Pass 1b (late-reviewer delta)

Second wave after [#65](https://github.com/Shangmin-Chen/worksisyphus/issues/65)–[#76](https://github.com/Shangmin-Chen/worksisyphus/issues/76). Same HEAD `b654120`. Source: [`_drafts/r3b-late-reviewer-delta.md`](_drafts/r3b-late-reviewer-delta.md).

| # | Title |
|---|-------|
| [78](https://github.com/Shangmin-Chen/worksisyphus/issues/78) | Publish and persist are two transactions |
| [79](https://github.com/Shangmin-Chen/worksisyphus/issues/79) | Fetch timeout fail-opens on stale `origin/main` — remaining hole after #51 |
| [80](https://github.com/Shangmin-Chen/worksisyphus/issues/80) | Selection guardrails are optimizer-only; `--plan` is unenforced |
| [81](https://github.com/Shangmin-Chen/worksisyphus/issues/81) | `real_profile` still launders the fixture; placeholder contact still renders |
| [82](https://github.com/Shangmin-Chen/worksisyphus/issues/82) | `export --force` can overwrite `profile.json` with a hollow DB |
| [83](https://github.com/Shangmin-Chen/worksisyphus/issues/83) | Trim guts the last remaining project before experience bullets |
| [84](https://github.com/Shangmin-Chen/worksisyphus/issues/84) | Policy gates never scan `profile.json`; skipped gates score 10/10 |
| [85](https://github.com/Shangmin-Chen/worksisyphus/issues/85) | Turso is last-snapshot-wins; append-only audit is local-only |
