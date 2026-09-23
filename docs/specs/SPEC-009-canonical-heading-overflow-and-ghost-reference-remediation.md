# SPEC-009: Canonical Heading Overflow Prevention and Ghost Reference Remediation

| Field | Value |
|---|---|
| **Spec ID** | `SPEC-009` |
| **Title** | Canonical Heading Overflow Prevention and Ghost Reference Remediation |
| **Status** | `Active` |
| **Author** | Simon Chen & Antigravity |
| **Created** | 2026-09-23 |
| **Updated** | 2026-09-23 |
| **Supersedes** | None |
| **Superseded By** | None |
| **Related Issues/PRs** | PR #96, PR #97 |

---

## 1. Context & Problem Statement

Following the hexagonal refactoring and legacy service pruning in SPEC-007 and SPEC-008, two stability defects were discovered during a comprehensive architectural audit:

1. **Horizontal Heading Overflow & ATS Date Collision**:
   - In Jake's template (`source_of_truth_resume.tex`), `\resumeProjectHeading` formats project titles and dates using a single-row, two-column tabular layout:
     ```latex
     \newcommand{\resumeProjectHeading}[2]{
         \item
         \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
           \small#1 & #2 \\
         \end{tabular*}\vspace{-7pt}
     }
     ```
   - In `profile.json`, the project `crime-mapper` had a compound dual-title joined by a slash:
     `"name": "Crime Analytics \\& Forecasting Platform / Crime-Mapper Boston"` (60 chars) combined with a 51-character tech stack (`"tech": "Python, Streamlit, Prophet, Scikit-learn, GeoPandas"`).
   - Because the left column is single-line without wrapping, this produced an overfull hbox of 117.0pt on canonical compilation. The text spilled over the right column (`{December 2024}`), causing PDF text extraction to extract `GeoPandasDecember 2024` with zero whitespace. This triggered an immediate ATS date check failure (`MERGED_DATE_RE`).
2. **Ghost References to Decommissioned SQLite Layer**:
   - Following the retirement of SQLite in PR #95 / SPEC-008, error messages in `profile_loader.py` and `latex.py` continued to instruct users and agents to execute `uv run worksisyphus db export-profile` when `profile.json` or contact fields were missing.
   - Unit tests in `tests/test_profile.py` asserted on these obsolete strings, and internal helper functions in `application.py` retained references to unused database paths.

This specification documents the immediate stabilization fixes for both defects. Architectural extensions (such as auto-apply submission ports and candidate screening question banks) are distinct features and remain scoped for future specifications.

---

## 2. Invariants & Bounded Rules

1. **Zero Horizontal Overflow Invariant**: Every compiled resume (tailored 1-pagers and the 3-page canonical database view) must compile with 0 overfull hboxes > 2pt. Project headings must fit comfortably within the 0.97\textwidth tabular budget.
2. **Jake's Template Preamble Verbatim**: The LaTeX preamble in `source_of_truth_resume.tex` remains unedited; fit is achieved by selecting or proposing concise content, never by changing font sizes or margins.
3. **Select, Propose, Never Write**: Changes to `profile.json` content require explicit operator approval. (Approved by Simon Chen on 2026-09-23).
4. **Honest Exception Contracts**: Error messages must reflect live system realities and never reference dead tools, deleted commands, or phantom databases.

---

## 3. Architecture & Implementation

### 3.1 Profile Heading Normalization (`PR #96`)
- `profile.json` and `tests/fixtures/profile.json` normalize `crime-mapper`'s title from the compound dual-title:
  ```json
  "name": "Crime Analytics \\& Forecasting Platform / Crime-Mapper Boston"
  ```
  to the concise title:
  ```json
  "name": "Crime Analytics \\& Forecasting Platform"
  ```
- This reduces header length by 23 characters, keeping the tabular row well within the horizontal boundary (0 overfull hboxes).
- `tex_files/Simon_Chen_Resume_Compiled.tex` is updated with the clean rendered TeX.

### 3.2 Ghost Error Message Remediation (`PR #97`)
- **`profile_loader.py`**:
  Updated `FileNotFoundError` message when `profile.json` is missing:
  ```python
  if not path.is_file():
      raise FileNotFoundError(
          f"Profile not found: {path}. Ensure profile.json exists in the repository root or provide a valid path."
      )
  ```
- **`latex.py`**:
  Updated `ValueError` message when a required contact field is empty:
  ```python
  if not getattr(contact, field_name, "").strip():
      raise ValueError(
          f"Cannot render a resume header: contact.{field_name} is empty. A resume "
          f"missing it cannot be answered; fix profile.json by providing a valid contact.{field_name} "
          f"rather than shipping a header without it."
      )
  ```
- **`application.py`**:
  - Removed dead `_resolve_db_path()` helper.
  - Renamed `cross_check_contact_against_db` to `verify_contact_block` to honestly describe its filesystem validation role. Retained `cross_check_contact_against_db` as a backward-compatibility alias.

---

## 4. Alternatives Considered & Trade-offs

| Alternative | Pros | Cons | Decision |
|---|---|---|---|
| **Modify `\resumeProjectHeading` to wrap lines** | Accommodates arbitrarily long titles. | Modifies Jake's LaTeX preamble; introduces inconsistent line spacing; violates Bounded Rule 2. | **Rejected**: Resume titles should be concise. |
| **Truncate project names at render time** | Automatically prevents overflows. | Violates "Select, propose, never write" rule by mutating resume content dynamically. | **Rejected**: Content must be curated at the source. |
| **Shorten title in `profile.json` with user approval** | 100% compliant with bounded rules; preserves Jake's template; zero overfull hboxes. | Requires user sign-off for content change. | **Accepted**: Approved by operator and resolves root cause cleanly. |

---

## 5. Verification & Testing Plan

1. **Canonical Build**:
   - `uv run worksisyphus compile` produces 0 overfull hboxes at line 222.
   - `test_compiled_resume_ats_extraction` verifies that `{December 2024}` extracts with preceding whitespace.
   - `test_compiled_resume_passes_all_gates` passes with 0 gate failures.
2. **Error Message Verification**:
   - `tests/test_profile.py`: `test_missing_profile_raises_instead_of_falling_back` asserts on `"Ensure profile.json exists"`.
3. **Full Quality Suite**:
   - All 204 tests pass (0 skipped, 0 failed).
   - Strict mypy, ruff check, and ruff format all pass cleanly.
