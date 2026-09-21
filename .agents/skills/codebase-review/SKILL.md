---
name: codebase-review
description: >-
  Conducts a comprehensive architectural, code quality, and invariant review of worksisyphus.
  Use this skill whenever the user asks to review the codebase, check for technical debt, slop,
  or over-engineering, audit quality gates, or generate a date-stamped review in docs/reviews/<YYYY-MM-DD>_review.md.
---

# Codebase & Architecture Review Skill

This skill guides the agent in performing rigorous, systematic code and architecture reviews for the `worksisyphus` repository. It verifies compliance with core bounded rules, checks hexagonal architecture boundaries, detects over-engineering, and documents findings in `docs/reviews/<YYYY-MM-DD>_review.md`.

---

## Review Scope & Verification Checklist

Every review must evaluate the codebase across five key pillars:

### 1. Bounded Rules & Core Invariants (`GEMINI.md` / `CLAUDE.md`)
- [ ] **1-Page Guarantee**: Tailored resumes compile to exactly 1 page; mechanical trim loop terminates deterministically without shrinking fonts or margins.
- [ ] **Jake's Template**: `source_of_truth_resume.tex` preamble is preserved verbatim in memory; no custom LaTeX margin squeezing.
- [ ] **Filename Conventions**: Delivered employer resumes are strictly named `Simon_Chen_Resume.pdf`; compiled canonical reference is `Simon_Chen_Resume_Compiled.pdf`.
- [ ] **Policy Gates**:
  - No GPA metrics in output (`check_gpa_gate`).
  - No piracy-adjacent tooling names (Sonarr, Radarr, Jellyfin, etc.) or fake-smelling metrics (`check_banned_content_gate`).
  - No unrendered LaTeX leak (`check_latex_leak_gate`).
  - Content density passes (`check_density_gate`).
- [ ] **Selection Guardrails**:
  - `persephone` prioritized for systems/infra/quant roles.
  - Weak projects (`fitness-tracker`, `spark-food-waste`, `ml-marketplace`) gated to matching domains.
  - `personal-website` excluded from systems/backend/quant roles.
  - `bu-engineering-it` excluded from pure SWE roles.
- [ ] **Select, Propose, Never Write**: Code selects existing slugs; does not silently author or reword resume bullets.

### 2. Hexagonal Architecture (Ports, Adapters, Core)
- [ ] **Core Domain Purity**: `src/worksisyphus/core/domain/` has zero external dependencies (no disk I/O, no network, no subprocess).
- [ ] **Dependency Inversion**: Core use cases (`pipeline`, `application`, `gates`) accept injected ports (`CompilerPort`, `AtsExtractorPort`, `StoragePort`, `GitGuardPort`).
- [ ] **Adapter Decoupling**: External integrations (pdflatex, pdfminer, SQLite, git) live cleanly in `adapters/` without leaking into core.
- [ ] **Facade Integrity**: Root modules (`src/worksisyphus/*.py`) remain thin backward-compatibility facades forwarding to core/adapters.

### 3. Over-Engineering Watch
- [ ] **Accidental Complexity**: Ensure no enterprise distributed patterns (e.g. multi-node sync, two-phase commits, distributed event ledgers) creep into a single-user resume compiler.
- [ ] **Honest Contracts**: Avoid mock/stub scoring mechanisms that return fake numbers (e.g. hardcoded 97.5 scores).
- [ ] **Fail-Closed Guarantees**: Errors and overflow conditions fail closed rather than silently publishing degraded outputs.

### 4. Quality Gates & Diagnostics
- [ ] **Test Suite**: `uv run python -m pytest tests/ -q` passes 100%.
- [ ] **Strict Typing**: `uv run mypy src/ tests/` reports zero errors.
- [ ] **Formatting & Linting**: `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/` are clean.

---

## Workflow Steps

1. **Run Diagnostics**:
   ```bash
   uv run ruff check src/ tests/
   uv run mypy src/ tests/
   uv run python -m pytest tests/ -q
   ```
2. **Inspect Recent Changes & Git Status**:
   ```bash
   git status
   git log -n 5 --oneline
   ```
3. **Audit Against the Checklist**:
   Inspect code and diffs against the five review pillars above.
4. **Generate the Review Document**:
   - Determine today's date (`YYYY-MM-DD`).
   - Create or update the review file at:
     `docs/reviews/<YYYY-MM-DD>_review.md`
   - Use the structure outlined below.
5. **Report Summary to User**:
   Provide an executive summary of findings, highlighting any open risks or action items.

---

## Review Document Format (`docs/reviews/<YYYY-MM-DD>_review.md`)

```markdown
# Architecture & Code Review — <YYYY-MM-DD>

## Executive Summary
A concise overview of the review findings, current commit/HEAD, and overall codebase health.

## Diagnostics Status
- **Pytest**: Passed X / X
- **Mypy**: Clean (73+ source files)
- **Ruff**: Clean

## Architecture & Boundary Health
Evaluation of Hexagonal boundaries (Core Domain, Ports, Adapters, Facades).

## Invariant & Bounded Rules Audit
Status of the 1-page guarantee, quality gates, Jake's template, selection guardrails, and ATS compliance.

## Over-Engineering & Simplicity Assessment
Analysis of codebase simplicity, dead code, redundant abstractions, or unwarranted complexity.

## Detailed Findings
List of specific observations categorized by severity:
- **High**: Invariant violations, fail-open gates, silent data corruption risks.
- **Medium**: Incomplete error contracts, leaky abstractions, missing tests.
- **Low / Note**: Code cleanup, naming, minor documentation drift.

## Action Items & Recommendations
Prioritized list of next steps.
```
