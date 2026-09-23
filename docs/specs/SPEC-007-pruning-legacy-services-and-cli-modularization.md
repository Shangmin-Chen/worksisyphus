# SPEC-007: Pruning Legacy Services and CLI Modularization

| Field | Value |
|---|---|
| **Spec ID** | `SPEC-007` |
| **Title** | Pruning Legacy Services (Turso, HackerRank) and CLI Architecture Modularization |
| **Status** | `Active` |
| **Author** | Simon Chen & Antigravity |
| **Created** | 2026-09-23 |
| **Updated** | 2026-09-23 |
| **Supersedes** | None |
| **Superseded By** | None |
| **Related Issues/PRs** | PR #90, PR #91 |

---

## 1. Context & Problem Statement

Over several months of development, `worksisyphus` accumulated extraneous external integrations and architectural sprawl that compromised its core philosophy: an offline, fast, deterministic, self-contained resume compiler.

Specifically:
1. **Turso Cloud Replication & VCS Gatekeeping (`git_guard.py`)**:
   - Turso synchronization introduced external HTTP/network dependencies (`requests>=2.31.0`), cloud credential management, and flaky git branch/freshness gates (`git_guard.py`).
   - The user has established that `worksisyphus` operates locally, with local SQLite (`worksisyphus.db`) as the sole authoritative database store. Cloud replication added complexity without operational benefit.
2. **HackerRank Hiring-Agent Pipeline (`hiring_agent.py`, `roles/`)**:
   - HackerRank evaluation required remote synchronization (`upstream_manifest.json`, `--check-upstream`), 8 distinct role templates with Jinja criteria files, and external rubric parsing.
   - This was replaced by deterministic ATS keyword extraction and rubric scoring in `core/use_cases/evaluator.py` and `optimizer.py`. The legacy HackerRank infrastructure remained as dead weight.
3. **Monolithic CLI Router (`commands.py`)**:
   - `commands.py` had ballooned to 626 lines, mixing argparse definitions, domain calls, database queries, terminal formatting, and error handling for 10 subcommands in a single sprawling module.
   - This hindered maintainability, modular testing, and readability.

---

## 2. Invariants & Bounded Rules

1. **Strict 1-Page Guarantee**: All resume outputs must strictly compile to 1 page with 0 overfull hboxes. Pruning and modularization must not touch Jake's LaTeX rendering invariants.
2. **Deterministic Offline Operation**: No network requests (`requests` library removed). All compilation, ATS verification, scoring, and database interactions must be 100% offline.
3. **Local SQLite Authority**: `worksisyphus.db` is the single source of persistence. Database schema and operations remain fully functional locally without cloud push steps.
4. **Backward Compatibility & Fail-Safe CLI**:
   - Legacy CLI flags (`--no-sync`, `--allow-branch`, `--no-git-check`) are accepted as silent no-ops so existing scripts or automated tooling do not fail with unrecognized argument errors.
   - Public symbols on `worksisyphus.cli` and `commands` are preserved to maintain test fixture and monkeypatch compatibility.

---

## 3. Architecture & Implementation

### 3.1 Retirement of Turso and VCS Guarding
- **Deleted Modules**:
  - `src/worksisyphus/git_guard.py`
  - `src/worksisyphus/adapters/outbound/git/`
  - `src/worksisyphus/ports/vcs.py`
  - `tests/test_git_guard.py`
- **Dependency Pruned**:
  - `requests>=2.31.0` removed from `pyproject.toml`.
- **Storage Port & Persistence Adapter**:
  - `StoragePort` in `src/worksisyphus/ports/storage.py` purged of `sync_cloud`, `allow_branch`, and `no_git_check`.
  - `SqliteStorageAdapter` in `src/worksisyphus/adapters/outbound/persistence/sqlite.py` streamlined to local SQLite operations only (`SqliteTursoAdapter` retained as backward-compatibility alias).
  - Turso SQL synchronization scripts (`DROP_ALL_SQL`, `build_sync_sql`, `sync_to_turso`) completely deleted.
  - `application.py`: `_sync_cloud` deleted; `apply` records to `worksisyphus.db` and completes without external cloud synchronization.

### 3.2 Retirement of HackerRank Hiring-Agent Pipeline
- **Deleted Modules & Assets**:
  - `src/worksisyphus/hiring_agent.py`
  - `src/worksisyphus/core/use_cases/hiring_agent.py`
  - `src/worksisyphus/ports/rubrics.py`
  - `src/worksisyphus/adapters/outbound/filesystem/rubrics_loader.py`
  - `src/worksisyphus/core/domain/scoring.py` (HackerRank models: `Category`, `CategoryScore`, `Deductions`, `Role`, `synthesize_role_rubric`)
  - `src/worksisyphus/roles/` directory (all 8 role subdirectories and `upstream_manifest.json`)
  - `tests/test_hiring_agent.py`
- **Evaluator & Optimizer Consolidation**:
  - `src/worksisyphus/core/use_cases/evaluator.py`: Pure deterministic scoring engine evaluating Role Alignment (0–40), Technical Depth (0–30), Impact & Evidence (0–20), and Quality Gate Compliance (0–10).
  - `src/worksisyphus/core/use_cases/optimizer.py`: Knapsack combinatorial optimizer scoring candidate plans deterministically using `evaluator.py`.

### 3.3 CLI Modularization (`commands.py` Decomposition)
`src/worksisyphus/adapters/inbound/cli/commands.py` is refactored from a 626-line monolith into a ~60-line top-level router that delegates subcommand parsing and execution to dedicated modules:

```text
src/worksisyphus/adapters/inbound/cli/
├── commands.py             # Top-level router and backward-compatibility facade
├── helpers.py              # Shared CLI helpers (InputReader, column formatting, etc.)
└── handlers/
    ├── apply.py            # 'apply' subcommand handler
    ├── backfill.py         # 'backfill-evals' subcommand handler
    ├── compile_cmd.py      # 'compile' subcommand handler
    ├── db.py               # 'db' (init, sync, status, history, export) subcommand handler
    ├── evaluate.py         # 'evaluate' subcommand handler
    ├── index.py            # 'index' subcommand handler
    ├── optimize.py         # 'optimize' subcommand handler
    ├── status.py           # 'status' and 'update-status' subcommand handlers
    ├── tailor.py           # 'tailor' preview subcommand handler
    └── validate.py         # 'validate' subcommand handler
```

Each handler exposes:
- `register(subparsers)`: Defines arguments and flags for the subcommand.
- `handle(args, read_input) -> int`: Executes the subcommand logic and returns an integer exit code.

---

## 4. Verification & Testing

1. **Test Suite**:
   - `uv run pytest tests/ -q`: All 232 test cases pass in under 1 second.
   - Tests previously asserting Turso sync warnings or HackerRank output updated to reflect local SQLite and deterministic ATS evaluation reports.
2. **Linting & Formatting**:
   - `uv run ruff check .`: Clean, 0 errors.
   - `uv run ruff format --check .`: Clean, 91 source files properly formatted.
3. **Type Checking**:
   - `uv run mypy src/ tests/`: Strict type check passes with 0 errors across all 76 source files.

---

## 5. Rollout & Compatibility

- **Local Development**: No disruption. SQLite commands (`worksisyphus db status`, `db init`, `db sync`) continue working with identical local semantics.
- **Removed Network Surface**: Eliminating `requests` eliminates supply-chain surface and removes network dependency from test and build pipelines.
