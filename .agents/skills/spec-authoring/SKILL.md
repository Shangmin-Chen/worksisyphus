---
name: spec-authoring
description: >-
  Standard for authoring, numbering, and maintaining technical specifications, architectural decision
  records, and system invariants in docs/specs/. Use this skill whenever proposing architectural
  changes, documenting invariants or workflows, or tracking technical decisions with incremental IDs.
---

# Technical Specification Authoring Skill

This skill guides agents and engineers in authoring, numbering, and maintaining technical specifications, system invariants, and architectural decision records (ADRs) in `docs/specs/`.

Every specification in `worksisyphus` receives a permanent, monotonically increasing sequential identifier (`SPEC-XXX`), ensuring historical traceability, immutable architectural context, and cross-reference stability across git history, issues, and pull requests.

---

## Core Principles

1. **Monotonically Increasing Sequential IDs**:
   - Every specification must use the format `SPEC-XXX-<kebab-title>.md`, where `XXX` is a zero-padded 3-digit integer (e.g. `SPEC-001`, `SPEC-002`, `SPEC-003`).
   - IDs are strictly unique and never recycled or renumbered.
2. **Immutable History**:
   - Specifications are append-only records of design decisions and system invariants at a point in time.
   - When an existing spec is superseded by a major architectural change or deprecation, do NOT delete or rewrite its core historical conclusions. Instead:
     - Update its header status to `Superseded` and link to the new spec (`Superseded by: [SPEC-YYY](file://...)`).
     - Author the new specification with the next available incremental ID.
3. **Canonical Index Registry (`docs/specs/README.md`)**:
   - Every spec MUST be registered in the catalog table in `docs/specs/README.md`.
   - The catalog lists: ID, Title, Status, Created Date, Target Area, and Summary.
4. **Deterministic and Concrete**:
   - Reference exact commit hashes (7 hex chars), file paths, and function signatures.
   - Differentiate clearly between shipped code on `main`, unmerged feature branches, and retired/dead patterns.

---

## Spec Lifecycle States

Each spec header includes a `Status` field with one of the following states:

| Status | Description |
|--------|-------------|
| `Draft` | Under active formulation, gathering feedback or exploring options. |
| `Proposed` | Finalized proposal awaiting review or implementation sign-off. |
| `Accepted` | Approved design, ready for or actively undergoing implementation. |
| `Active` | Implemented and currently representing live system invariants / architecture. |
| `Superseded` | Replaced by a newer specification (`SPEC-YYY`). Kept for historical context. |
| `Retired` | Decommissioned feature or workflow no longer present in the codebase. |

---

## Workflow: Authoring a New Specification

### Step 1: Determine the Next Incremental ID
1. Inspect the index table in `docs/specs/README.md` or list existing files in `docs/specs/`:
   ```bash
   ls docs/specs/SPEC-*.md
   ```
2. Identify the highest existing integer `N`.
3. The new spec ID will be `SPEC-` followed by `N + 1` zero-padded to 3 digits (e.g. if the highest is `SPEC-005`, the next is `SPEC-006`).

### Step 2: Create the Spec File
Create the file at `docs/specs/SPEC-XXX-<kebab-title>.md` using the standard template below.

### Step 3: Register in `docs/specs/README.md`
Add the new spec to the index table in `docs/specs/README.md`, including:
- Link to spec file
- Descriptive Title
- Lifecycle Status (`Draft`, `Proposed`, `Active`, etc.)
- Date (`YYYY-MM-DD`)
- Target Area / Scope
- 1-2 sentence executive summary

---

## Standard Specification Template

```markdown
# SPEC-XXX: <Title>

| Field | Value |
|-------|-------|
| **Spec ID** | `SPEC-XXX` |
| **Title** | <Descriptive Title> |
| **Status** | `Draft` \| `Proposed` \| `Active` \| `Superseded` \| `Retired` |
| **Author** | <Author Name or Agent> |
| **Created** | <YYYY-MM-DD> |
| **Updated** | <YYYY-MM-DD> |
| **Supersedes** | None \| `SPEC-YYY` |
| **Superseded By** | None \| `SPEC-YYY` |
| **Related Issues/PRs** | #..., PR #... |

---

## 1. Context & Problem Statement
*Why is this specification needed? What problem, friction, or architectural evolution does it address?*

## 2. Invariants & Bounded Rules
*What fundamental system guarantees must never be broken? (e.g., 1-page PDF constraint, Jake's template preservation, fail-closed gates, determinism).*

## 3. Proposed Architecture & Design
*Detailed technical design, module boundaries, data flow diagrams, interfaces, and port/adapter contracts.*

### 3.1 Domain Models & Ports
*Define pure domain entities and abstract protocols.*

### 3.2 Adapters & Implementations
*Define concrete external integrations (CLI, storage, compilers, parsers).*

## 4. Alternatives Considered & Trade-offs
*What alternatives were explored? Why were they rejected? What are the trade-offs of the chosen approach?*

## 5. Verification & Testing Plan
*How will this design be verified? (Unit tests, fixture boundaries, gate checks, CI pipeline).*

## 6. Migration, Compatibility & Rollout
*Impact on existing files, schemas, and CLI commands. How will legacy data or callers transition?*
```

---

## Quality Checklist for Specifications

Before opening a PR for a new or updated specification:
- [ ] ID is strictly sequential and padded to 3 digits (`SPEC-001`, `SPEC-002`, etc.).
- [ ] Registered in `docs/specs/README.md` index table.
- [ ] Header metadata table is complete (Spec ID, Title, Status, Created Date, Author).
- [ ] Grounded in verifiable facts (exact commit hashes, file paths, tests).
- [ ] Respects core bounded rules (`GEMINI.md` / `CLAUDE.md`).
- [ ] Markdown links use proper relative or github-style paths.
