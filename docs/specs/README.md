# Technical Specifications & Architecture Decision Records (ADRs)

This directory houses the canonical, sequential specifications, system invariants, and architectural decision records for `worksisyphus`.

All specifications are tracked with permanent sequential identifiers (`SPEC-XXX`). To propose or author a new specification, follow the instructions in [`.agents/skills/spec-authoring/SKILL.md`](file://../../.agents/skills/spec-authoring/SKILL.md).

---

## Specifications Index

| Spec ID | Title | Status | Date | Scope | Description |
|:---|:---|:---:|:---:|:---|:---|
| [**SPEC-001**](SPEC-001-chronological-timeline.md) | Chronological Timeline & Historical Milestones | `Active` | 2026-09-13 | Git History / Milestones | Detailed milestone evolution across all eras, from original LaTeX shop to modern compiler. |
| [**SPEC-002**](SPEC-002-system-invariants.md) | System Invariants & Bounded Rules | `Active` | 2026-09-13 | Core Invariants | Canonical list of immutable rules, landed commit anchors, and operator traps. |
| [**SPEC-003**](SPEC-003-hexagonal-architecture.md) | Hexagonal Architecture, Ports/Adapters & Legacy Topology | `Active` | 2026-09-21 | Architecture | Hexagonal Ports/Adapters/Core modularization, data flow, and dead layout tombstones. |
| [**SPEC-004**](SPEC-004-agent-workflows-and-cli.md) | Agent Workflows, CLI Registry & Operational Rules | `Active` | 2026-09-13 | CLI / Workflows | Operational instructions for autonomous agents, command registry (live and retired). |
| [**SPEC-005**](SPEC-005-documentation-drift.md) | Documentation Drift, Code Disagreements & Unmerged Branches | `Active` | 2026-09-13 | Quality / Drift | Comprehensive audit of divergence between prose documentation, code reality, and unmerged PRs. |
| [**SPEC-006**](SPEC-006-ats-keyword-adaptation-and-compiler.md) | Truth-Preserving ATS Keyword Adaptation & Configurable Compiler Architecture | `Active` | 2026-09-23 | Architecture / Compiler | Truth-preserving keyword alignment, configurable LaTeX compiler (`CompilerConfig`), density ladder, and mechanical GPA suppression. |
| [**SPEC-007**](SPEC-007-pruning-legacy-services-and-cli-modularization.md) | Pruning Legacy Services (Turso, HackerRank) and CLI Architecture Modularization | `Active` | 2026-09-23 | Architecture / Cleanup | Pruning of Turso cloud replication, requests dependency, and HackerRank evaluator in favor of local SQLite and modular CLI router. |
| [**SPEC-008**](SPEC-008-pure-filesystem-architecture-and-sqlite-decommissioning.md) | Pure Filesystem Architecture & SQLite Decommissioning | `Active` | 2026-09-23 | Architecture / Persistence | Decommissioning of SQLite persistence layer in favor of pure, standalone filesystem architecture (`applications/` and `profile.json`). |
| [**SPEC-009**](SPEC-009-canonical-heading-overflow-and-ghost-reference-remediation.md) | Canonical Heading Overflow Prevention and Ghost Reference Remediation | `Active` | 2026-09-23 | Reliability / Bugfix | Resolution of canonical project heading horizontal overflow (crime-mapper) and remediation of ghost SQLite CLI error messages. |
| [**SPEC-010**](SPEC-010-raw-job-ingestion-and-etl-compiler.md) | Raw Job Ingestion & ETL Posting Compiler | `Accepted` | 2026-09-23 | Architecture / Ingestion | Decoupled raw job intake engine, verbatim pre-cleaning scratch bridge, and structured ETL posting compiler. |

---

## Specification Lifecycle

- `Draft`: Specification in formulation; ideas and interfaces being explored.
- `Proposed`: Completed design undergoing review.
- `Accepted`: Approved specification scheduled for or in implementation.
- `Active`: Live specification reflecting current production codebase behavior.
- `Superseded`: Deprecated or replaced by a subsequent sequential specification (`SPEC-YYY`).
- `Retired`: Historical feature or workflow no longer present in the system.

---

## Operating Guidelines

1. **Sequential Incremental IDs**: Next available spec ID is **`SPEC-011`**.
2. **Never Rewrite Past Decisions**: Prior specs are immutable records of design rationale at their creation time. When requirements shift or architecture evolves, create a new spec and mark the predecessor as `Superseded`.
3. **Skill Reference**: See [`.agents/skills/spec-authoring/SKILL.md`](file://../../.agents/skills/spec-authoring/SKILL.md) for templates and authoring guidelines.
