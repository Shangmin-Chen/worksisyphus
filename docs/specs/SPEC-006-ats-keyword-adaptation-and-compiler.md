# SPEC-006: Truth-Preserving ATS Keyword Adaptation & Configurable Compiler Architecture

| Field | Value |
|---|---|
| **Spec ID** | `SPEC-006` |
| **Title** | Truth-Preserving ATS Keyword Adaptation & Configurable Compiler Architecture |
| **Status** | `Accepted` |
| **Author** | Simon Chen / Antigravity Agent Synthesis |
| **Created** | 2026-09-21 |
| **Updated** | 2026-09-21 |
| **Supersedes** | None (Refines Invariant #4 in `SPEC-002`) |
| **Superseded By** | None |
| **Related Issues/PRs** | #74, #75, #76, #84 |

---

## 1. Context & Problem Statement

The fundamental purpose of a tailored resume is to **pass Applicant Tracking Systems (ATS) and reach the hands of technical recruiters and hiring managers**.

In real-world recruiting:
1. **ATS Filtering & Recruiter Boolean Searches**: Platforms like Workday, Taleo, Greenhouse, Lever, and Ashby perform algorithmic keyword matching, n-gram extraction, and recruiter boolean queries. If a job posting demands *"low-latency streaming infrastructure"*, an applicant whose resume only says *"lock-free SPSC event ring in Cython/C++17 benchmarked at 584ns"* receives zero match points for that skill query, filtering the candidate out before a human engineer ever reads the technical benchmark.
2. **The Limitation of Pure Slug Selection**: The earlier invariant ("Select, propose, never write — pick slugs, never edit bullet text") treated bullet text as immutable strings. While this prevented LLM hallucination, it artificially crippled ATS discoverability: genuine engineering achievements could not be re-framed in the target job's vocabulary.
3. **Fragile Post-Hoc Quality Gates**: The system previously relied on post-compilation regex scanners (e.g. `GPA_RE`) searching rendered PDF text. This caused persistent false positives whenever software version numbers (`Rails 7.0`, `Python 3.11`) or engineering multipliers (`4.0x speedup`) appeared in bullet points.
4. **Avoiding Mirror Class Slop**: Artificially stripping fields from domain models (e.g. creating `EducationParam` that omits `gpa`) introduces unnecessary boilerplate. In compiler engineering, the data model holds the complete facts, while **compiler toggles and configuration flags** control code generation.

This specification establishes an architecture that combines **truth-preserving keyword adaptation** with a **configurable compiler (`CompilerConfig`)** that eliminates GPA by default via compilation toggles and provides a graceful density ladder for 1-page fitting.

---

## 2. Invariants & Bounded Rules

1. **Anti-Hallucination Invariant (Truth-Preservation)**:
   - Every metric (`\$8K`, `584ns`, `75\%`, `20+ teams`, `500+ matches`), employer name, title, date range, and underlying technology must originate strictly from `profile.json`.
   - The agent is permitted to adapt **vocabulary, phrasing, and emphasis** to align with the target job description, but may **never** invent technologies Simon did not use, fabricate metrics, or claim unperformed work.

2. **Compiler Toggle for GPA Control**:
   - `Education` naturally supports optional GPA (`gpa: str | None = None`).
   - The compiler accepts `CompilerConfig` with `include_gpa: bool = False` by default.
   - During code generation, the compiler only emits the LaTeX GPA snippet if `config.include_gpa` is explicitly `True` AND `entry.gpa` is non-empty.
   - Because `include_gpa` defaults to `False`, no GPA is emitted in standard builds. Fragile post-hoc regex checks on PDF text are deleted.
   - If a specific application (e.g., quant finance or government defense) mandates GPA, the toggle can be set to `True` without altering the codebase.

3. **Jake's Template Preamble Immutability**:
   - The LaTeX preamble in `source_of_truth_resume.tex` remains verbatim and immutable.
   - Resumes fit on one page by selecting and prioritizing content, never by shrinking margins, altering line spacing, or reducing fonts.

4. **Deterministic 1-Page Guarantee & Graceful Density Ladder**:
   - Every employer-facing resume compiled into `applications/<date>_<stem>/Simon_Chen_Resume.pdf` must be exactly 1 page with no horizontal overflow (`overfull \hbox`).
   - Before aggressively dropping an entire project or bullet over a 1–2 line overflow, the compiler utilizes formatting toggles (e.g. condensing coursework, compacting skill groupings). If it still exceeds 1 page, it trims lowest-priority bullets and projects from the bottom.

---

## 3. System Architecture & Workflow

```mermaid
flowchart TD
    subgraph 1. Ingestion & ATS Keyword Extraction
        A["Job URL or JD Text"] --> B["Crawl URL / Ingest Posting"]
        B --> C["Extract Target Role & ATS Keywords<br/>(Hard skills, tools, domain n-grams)"]
    end

    subgraph 2. Ground-Truth Data
        P["profile.json<br/>(Verifiable metrics, dates, experiences, projects)"]
    end

    subgraph 3. Truth-Preserving Adaptation (Agent)
        C --> D["Agent Selection & Keyword Alignment"]
        P --> D
        D --> E["Draft Adapted Bullets<br/>(Canonical facts + JD vocabulary)"]
    end

    subgraph 4. ATS Verification Loop
        E --> F["Deterministic ATS Keyword Scorer"]
        C --> F
        F --> G{"ATS Keyword Match Target Met?<br/>(e.g., >= 85% coverage)"}
        G -- No --> D
        G -- Yes --> H["Validated Candidate Resume Payload"]
    end

    subgraph 5. Configurable Compiler (Python)
        H --> I["Custom Jake's Resume Compiler"]
        CFG["CompilerConfig<br/>(include_gpa=False, density toggles)"] --> I
        T["source_of_truth_resume.tex Preamble"] --> I
        I --> J["Render Body & Run pdflatex"]
        J --> K{"Page Count == 1<br/>and No Overfull?"}
        K -- No --> L["Density Ladder (condense coursework/skills) & Trim Bottom"]
        L --> J
        K -- Yes --> M["Final Simon_Chen_Resume.pdf"]
    end

    subgraph 6. Application Freeze
        M --> N["applications/<date>_<company>_<role>/"]
        H --> N
        B --> N
    end
```

---

## 4. Component Design

### 4.1 Ingestion & Context Extraction
- Accepts either raw job description text via stdin/argument or a direct job posting URL (`--url <link>`).
- If a URL is provided, the ingestion layer fetches and extracts the job title, company, required technologies, preferred tools, and domain keywords.

### 4.2 Truth-Preserving Adaptation (Agent Layer)
The agent maps canonical items from `profile.json` to the target requirements:
- **Bullet Framing**: Re-phrases the lead-in to match the JD's phrasing while keeping the core technical proof and metrics intact.
- **Example**:
  - *JD Query*: `"experience building low-latency streaming infrastructure"`
  - *Canonical Fact*: Persephone lock-free SPSC event ring in Cython/C++17, benchmarked at 584ns per enqueue.
  - *Adapted Output*: `"Architected low-latency streaming infrastructure using a lock-free SPSC event ring in Cython/C++17, benchmarked at 584ns per enqueue and 703ns per event drained."`

### 4.3 Deterministic ATS Keyword Scorer
An offline mathematical scorer that measures exact and synonym keyword density:
- Checks presence of required languages, frameworks, and domain phrases in the candidate text.
- Provides an objective **Keyword Coverage Score (0–100%)** recorded in `meta.json`.

### 4.4 Configurable Compiler (`CompilerConfig`)

The compiler uses a clean configuration model:

```python
from enum import Enum
from dataclasses import dataclass


class CourseworkMode(str, Enum):
    FULL = "full"  # Relevant Coursework: course1, course2... (standard)
    CONDENSED = "condensed"  # Compacted list (saves 1 line)
    NONE = "none"  # Omit coursework entirely (saves 2 lines)


@dataclass(frozen=True)
class CompilerConfig:
    # Content toggles
    include_gpa: bool = False  # Default False; set True if explicitly required
    coursework_mode: CourseworkMode = CourseworkMode.FULL
    include_locations: bool = True
    clickable_links: bool = True

    # Formatting density toggles
    compact_skills: bool = False  # Combine skill categories into inline format
    compact_header: bool = False  # Inline contact details
```

### 4.5 The Line-Fitting Density Ladder

When compiling to the mandatory 1-page target:
1. **Level 0 (Standard Render)**:
   - `include_gpa = False`, `coursework_mode = FULL`, `compact_skills = False`.
2. **Level 1 (Micro-Fitting — saves 1 line)**:
   - If over 1 page by $\le 1$ line, set `coursework_mode = CONDENSED`.
3. **Level 2 (Compact Skills — saves 1–2 lines)**:
   - If still over 1 page, set `compact_skills = True`.
4. **Level 3 (Omit Coursework — saves 1–2 lines)**:
   - If still over 1 page, set `coursework_mode = NONE`.
5. **Level 4 (Deterministic Structural Trim)**:
   - If formatting toggles are exhausted and the document still exceeds 1 page, trim the lowest-ranked bullet or project from the bottom up.

---

## 5. Migration & Rollout Plan

1. **Step 1: Implement `CompilerConfig` & Generator Toggles**
   - Add `CompilerConfig` to `core/rendering/latex.py` (or domain models).
   - Update `_education()` in `latex.py` to conditionally render GPA based on `config.include_gpa` (default `False`).
   - Add `coursework_mode` and `compact_skills` density toggles.
   - Delete brittle `GPA_RE` regex checks in `gates.py`.

2. **Step 2: Implement Offline ATS Keyword Scorer**
   - Create `core/domain/ats_matcher.py` to extract keywords and compute keyword coverage percentage.
   - Unit test scorer with fixture data.

3. **Step 3: Implement Job Link Ingestion**
   - Add URL fetching and text extraction adapter.

4. **Step 4: Update Documentation & Tests**
   - Verify `pytest`, `mypy`, `ruff check`, and `ruff format --check .` pass with 100% clean status.
   - Open Pull Request.
