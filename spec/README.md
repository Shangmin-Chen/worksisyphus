# Architecture review specs

This directory is the public record of the 2026-09-13 architecture/slop review of worksisyphus.

The project’s contract is fail-closed and mechanically enforced: one page, Jake’s template untouched, select-never-write, quality gates before a resume is considered delivered. This pass asked whether the code still does that at HEAD `b654120` (`review/architecture-slop`).

## How to read

1. **[architecture-review-2026-09-13.md](architecture-review-2026-09-13.md)** — grouped findings, each group linked to the GitHub issue opened from it, plus the habits this pass kept seeing and a closed-issue verification table.
2. **[_drafts/r3-architecture-slop-findings.md](_drafts/r3-architecture-slop-findings.md)** — raw, de-duped reviewer dump. Kept as the source notes. Not the filing record; do not treat IDs like `F-RENDER-1` as issues.

Do not re-file open [#45](https://github.com/Shangmin-Chen/worksisyphus/issues/45) [#46](https://github.com/Shangmin-Chen/worksisyphus/issues/46) [#47](https://github.com/Shangmin-Chen/worksisyphus/issues/47) [#49](https://github.com/Shangmin-Chen/worksisyphus/issues/49) [#50](https://github.com/Shangmin-Chen/worksisyphus/issues/50) or the named bugs of open PRs [#52](https://github.com/Shangmin-Chen/worksisyphus/pull/52)–[#64](https://github.com/Shangmin-Chen/worksisyphus/pull/64).

## Issues opened this pass

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
