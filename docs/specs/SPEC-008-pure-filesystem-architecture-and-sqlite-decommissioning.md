# SPEC-008: Pure Filesystem Architecture & SQLite Decommissioning

| Field | Value |
|---|---|
| **Spec ID** | `SPEC-008` |
| **Title** | Pure Filesystem Architecture & SQLite Decommissioning |
| **Status** | `Active` |
| **Author** | Simon Chen & Antigravity |
| **Created** | 2026-09-23 |
| **Updated** | 2026-09-23 |
| **Supersedes** | Partially supersedes [SPEC-007](SPEC-007-pruning-legacy-services-and-cli-modularization.md) Section 3.1 (Local SQLite Authority) |
| **Superseded By** | None |
| **Related Issues/PRs** | PR #92, PR #93, PR #94, PR #95 |

---

## 1. Context & Problem Statement

In August 2026, an SQLite database layer (`worksisyphus.db`, `src/worksisyphus/db.py`, `adapters/outbound/persistence/sqlite.py`) was introduced to the repository. Its primary historical purpose was serving as a local staging buffer for remote Turso cloud synchronization (`DROP_ALL_SQL`, `sync_to_turso`).

Following the decommissioning of Turso cloud replication in PR #92, the local SQLite database remained. However, an architectural audit revealed that the SQLite persistence layer was entirely redundant with the repository's filesystem architecture:

1. **Redundant Source of Truth**:
   - Every application processed by `worksisyphus apply` is already frozen into an immutable directory at `applications/<YYYY-MM-DD>_<company>_<role>/`.
   - Each folder contains `Simon_Chen_Resume.pdf`, `jd.txt` (the raw posting), `plan.json` (the exact selected slugs), and `meta.json` (company, role, date, status, evaluation scores, contact verification).
   - Core CLI queries like `worksisyphus status` and `worksisyphus update-status` already operate directly on `applications/*/meta.json` files in the filesystem.
2. **Operator Usage Reality**:
   - Simon interacts with `worksisyphus` exclusively through autonomous AI agents (Antigravity / Claude Code) and targeted CLI commands (`apply`, `status`, `update-status`, `evaluate`).
   - Neither the user nor the operating agents ever executed SQL queries against `worksisyphus.db`.
3. **Circular Validation and Friction**:
   - The "Contact Cross-Check Gate" originally cross-checked `profile.json` contact information against the database before compiling. But the database itself was seeded directly from `profile.json`, making the check circular.
   - Maintaining the SQLite schema, migrations, connection handling, and sync commands required ~1,600 lines of code across `sqlite.py` (813 lines) and `test_db.py` (740 lines).

Consequently, the user directed that the entire SQLite layer be retired, establishing a pure, 100% standalone filesystem architecture.

---

## 2. Invariants & Bounded Rules

1. **Strict 1-Page Guarantee**: Tailored resume outputs must strictly compile to 1 page with 0 overfull hboxes. Jake's template LaTeX formatting and preamble remain untouched.
2. **Select, Propose, Never Write**: Slugs are selected from `profile.json`; resume content is never authored or altered by the compiler without explicit user sign-off.
3. **Pure Filesystem Authority**:
   - `profile.json` is the sole authoritative source of truth for candidate profile data.
   - `applications/<YYYY-MM-DD>_<stem>/` is the sole authoritative history of sent resumes and application state.
4. **Deterministic Gate Enforcement**:
   - Quality gates (ATS check, No-GPA, Banned Content, LaTeX Leaks, Content Density) continue to run deterministically on every compile.
   - Contact verification (`validate_contact`) validates candidate contact information directly against structure, format, and completeness rules without requiring a database file.
5. **No Network Dependencies**: Compilation, optimization, evaluation, and storage run completely offline with zero network requests.

---

## 3. Architecture & Implementation

### 3.1 Decommissioned Components
The following modules and test suites have been deleted:
- `src/worksisyphus/adapters/outbound/persistence/`: Decommissioned.
- `src/worksisyphus/ports/storage.py` (`StoragePort`): Decommissioned.
- `src/worksisyphus/db.py`: Decommissioned backward-compatibility facade.
- `src/worksisyphus/adapters/inbound/cli/handlers/db.py`: Decommissioned CLI subcommands (`db init`, `db sync`, `db status`, `db history`, `db export-profile`).
- `tests/test_db.py`: Decommissioned.
- `worksisyphus.db`: Removed from repository.

### 3.2 Simplified Hexagonal Architecture
With persistence ports removed, the system topology is streamlined:

```text
src/worksisyphus/
├── core/
│   ├── domain/         # models, trim rules, plan resolution, quality gates, scoring
│   ├── use_cases/      # application lifecycle, pipeline, optimizer, evaluator, gates
│   └── rendering/      # Jake's LaTeX resume renderer
├── ports/
│   ├── compiler.py     # CompilerPort (pdflatex execution)
│   └── ats.py          # AtsExtractorPort (PDF text extraction)
├── adapters/
│   ├── inbound/cli/    # Modular CLI handlers (apply, status, evaluate, etc.)
│   └── outbound/
│       ├── latex/      # pdflatex runner
│       └── pdf/        # PDF ATS text extractor
└── *.py                # backward-compatibility facades (application, cli, pipeline, etc.)
```

### 3.3 Application Lifecycle & Metadata Contract
- **Application Directory Freeze**:
  When `worksisyphus apply` executes, it renders and compiles the PDF directly into `applications/<date>_<stem>/Simon_Chen_Resume.pdf`, creates `plan.json`, `jd.txt`, and generates `meta.json`.
- **Contact Verification Format**:
  To maintain backward compatibility with downstream evaluation and historical records, `ContactCrossCheck.as_meta()` preserves the established JSON contract:
  ```json
  "contact_verification": {
    "rules_checked": true,
    "cross_checked_against_db": false,
    "database": "",
    "skip_reason": "Standalone filesystem mode: validated by validate_contact rules."
  }
  ```
- **Status Tracking**:
  `worksisyphus status` and `worksisyphus update-status` read and write directly to `applications/*/meta.json`. Repeat application grouping (`App#`) and stem disambiguation function purely via directory traversal.

---

## 4. Alternatives Considered & Trade-offs

| Alternative | Pros | Cons | Decision |
|---|---|---|---|
| **Retain local SQLite as optional audit cache** | Append-only SQL audit log preserved. | Redundant dual state; extra code and test maintenance; never used by agent or operator. | **Rejected**: Filesystem JSON already tracks full state and history. |
| **Flat SQLite file without filesystem folders** | Single DB file on disk. | Hard to inspect PDFs, JDs, and diff plans in standard Unix tools or git. | **Rejected**: Filesystem transparency is a core strength of worksisyphus. |
| **Pure Filesystem Architecture** | Zero database boilerplate, ~1,600 lines deleted, fast test runs (<1s), full transparency. | Relies on filesystem directory listings for status aggregation. | **Accepted**: Fits Simon's local workflow and CLI usage perfectly. |

---

## 5. Verification & Testing Plan

1. **Test Suite**:
   - `uv run python -m pytest tests/ -q`: All 202 test cases pass in ~0.84 seconds.
   - Database tests (`test_db.py`) removed; consistency tests updated to assert filesystem invariants.
2. **Linting & Code Quality**:
   - `uv run ruff check .`: Clean, 0 errors.
   - `uv run ruff format --check .`: Clean.
   - `uv run mypy src/ tests/`: Static type checking passes cleanly.
3. **Application End-to-End**:
   - `apply`, `status`, `update-status`, and `evaluate` commands operate seamlessly without any database connections.

---

## 6. Migration, Compatibility & Rollout

- **Historical Applications**: Existing `applications/<date>_<stem>/` directories and their `meta.json` files remain completely intact and compatible.
- **Removed Commands**: The `worksisyphus db` command group is removed. Documentation in `README.md`, `CLAUDE.md`, and `GEMINI.md` is updated to reflect the streamlined command suite.
- **Profile Recovery**: `profile.json` remains in the repository root (gitignored). If recovery is ever needed, it is backed up in the user's private data storage, eliminating the need for `db export-profile`.
