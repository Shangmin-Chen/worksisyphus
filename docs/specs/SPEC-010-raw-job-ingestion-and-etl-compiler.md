# SPEC-010: Raw Job Ingestion & ETL Posting Compiler

| Field | Value |
|---|---|
| **Spec ID** | `SPEC-010` |
| **Title** | Raw Job Ingestion & ETL Posting Compiler |
| **Status** | `Accepted` |
| **Author** | Simon Chen & Antigravity |
| **Created** | 2026-09-23 |
| **Updated** | 2026-09-23 |
| **Supersedes** | None |
| **Superseded By** | None |
| **Related Issues/PRs** | None (Foundational Intake Architecture) |

---

## 1. Context & Problem Statement

Historically, `worksisyphus apply` has been a passive resume compiler. Operators and autonomous agents are forced to manually open job postings in a browser, identify the company name and target role, copy the entire multi-paragraph job description, and pass it into the CLI via stdin (`--jd -`).

To transform `worksisyphus` into an autonomous career engine, the system requires an automated ingestion layer. However, job postings across the web suffer from severe format entropy:
- **Vendor Diversity**: Postings live across disparate applicant tracking systems (Greenhouse, Lever, Ashby, Workday) and custom corporate career portals.
- **Payload Bloat**: Modern career pages frequently contain 100,000+ characters of minified JavaScript bundles, tracking pixels, navigation headers, and CSS stylesheets.
- **LLM Paraphrasing & Hallucination Risks**: Forcing an LLM or chat agent to regenerate giant 10-page job descriptions into a terminal prompt risks lossy summarization, dropped requirements, shell-escaping syntax failures, and massive token waste.

This specification defines the first decoupled stage of the ingestion architecture: **Raw Job Ingestion & the ETL Posting Compiler**. 
Its scope is strictly limited to intake: fetching raw outside data, performing deterministic noise removal, preserving verbatim JD text via a file-based scratch bridge, and compiling raw data into a normalized, strongly-typed `JobPosting` domain object.

Downstream consumers (Lead Vault tracking and `apply --url` resume generation) are deliberately decoupled and specified in SPEC-011.

---

## 2. Invariants & Bounded Rules

1. **Verbatim Text Preservation**: The source job description must be captured and preserved byte-for-byte. The ingestion engine and agent must never summarize, paraphrase, or truncate job requirements.
2. **File-Based Scratch Bridge**: Giant multi-paragraph JD texts must never be piped as raw inline command-line arguments to avoid shell quoting breakage, buffer limits, and LLM output token exhaustion. Raw text flows from network to disk, and from disk to compiler.
3. **Offline Testability (CI Invariant)**: Ingestion and ETL tests must execute 100% offline with zero internet access, zero API keys, and sub-second speed using pre-recorded fixtures in `tests/fixtures/postings/`.
4. **Hexagonal Boundary Purity**: The core domain (`core/domain/`), resume compiler (`pipeline.py`), and LaTeX renderer (`latex.py`) remain completely network-free and decoupled from ingestion. Ingestion logic resides exclusively in `ports/ingestion.py` and `adapters/outbound/ingestion/`.
5. **Namespace Safety**: Company and role identifiers extracted during ETL must strictly conform to `slugify` rules (no underscores, safe for filesystem folder names).

---

## 3. Proposed Architecture & Design

```
   [ External Job URL ]
             │
             ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ 1. Raw Fetcher Adapter (adapters/outbound/ingestion/http)   │
  │ • urllib.request with standard browser User-Agent headers   │
  │ • Redirect following & SSL handling                         │
  │ • Explicit 10s timeout & 404/closed detection               │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ Raw bytes / text
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ 2. Pre-Cleaner & Scratch Bridge                             │
  │ • Strips <script>, <style>, <svg>, <noscript>, comments     │
  │ • html.unescape() for entities (&amp; -> &, &nbsp; -> ' ')  │
  │ • Writes verbatim JD to `.worksisyphus/scratch/current_jd`  │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ 3. ETL Posting Compiler (adapters/outbound/ingestion/etl)   │
  │ • Detects source: Greenhouse API / Lever / Ashby / HTML     │
  │ • Extracts: Company, Role, Location                         │
  │ • Extracts: Form Screening Questions (IDs, prompts, options)│
  │ • Agent/CLI override support (--company, --role)            │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
                   `JobPosting` Domain Object
  (company, role, jd_text, location, url, screening_questions, raw_payload)
```

### 3.1 Domain Models (`src/worksisyphus/core/domain/ingestion.py`)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScreeningQuestion:
    """A pre-screen question extracted from the job posting form."""

    question_id: str
    prompt: str
    question_type: str  # "text" | "textarea" | "select" | "boolean" | "file"
    required: bool
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class RawJobPayload:
    """Unprocessed network payload and metadata."""

    url: str
    raw_content: str
    content_type: str  # "application/json" | "text/html"
    source_hint: str  # "greenhouse" | "lever" | "ashby" | "generic"
    fetched_at: str


@dataclass(frozen=True)
class JobPosting:
    """Normalized, validated job opportunity ready for downstream consumption."""

    company: str
    role: str
    jd_text: str
    url: str
    location: str = ""
    source_type: str = "generic"
    screening_questions: tuple[ScreeningQuestion, ...] = ()
    raw_payload: dict[str, Any] = field(default_factory=dict)
```

### 3.2 Ports (`src/worksisyphus/ports/ingestion.py`)

```python
from typing import Protocol
from ..core.domain.ingestion import JobPosting, RawJobPayload


class RawFetcherPort(Protocol):
    """Outbound port for fetching raw posting content from the web."""

    def fetch(self, url: str, timeout: float = 10.0) -> RawJobPayload: ...


class JobTransformerPort(Protocol):
    """Port for compiling raw payloads into normalized JobPosting domain entities."""

    def transform(
        self,
        raw: RawJobPayload,
        company_override: str = "",
        role_override: str = "",
    ) -> JobPosting: ...
```

### 3.3 Outbound Adapters (`src/worksisyphus/adapters/outbound/ingestion/`)

1. **`http_fetcher.py` (`RawFetcherPort`)**:
   - Uses Python standard library `urllib.request`.
   - Injects browser headers (`User-Agent: Mozilla/5.0...`, `Accept: application/json, text/html`).
   - Automatically detects and routes ATS URLs:
     - Greenhouse URLs (`boards.greenhouse.io/<company>/jobs/<id>`) are automatically routed to Greenhouse's unauthenticated JSON API (`boards-api.greenhouse.io/v1/boards/<company>/jobs/<id>`).
     - Lever URLs (`jobs.lever.co/<company>/<id>`) are routed to Lever's public JSON API (`api.lever.co/v0/postings/<company>/<id>`).
     - Ashby URLs (`jobs.ashbyhq.com/<company>/<id>`) fetch public JSON posting data.
     - Custom URLs fetch raw HTML with redirect following.
2. **`pre_cleaner.py`**:
   - Parses HTML using stdlib `html.parser`.
   - Strips non-content elements (`<script>`, `<style>`, `<svg>`, `<nav>`, `<footer>`).
   - Converts structural tags (`<p>`, `<li>`, `<br>`, `<h1>`-`<h6>`) into clean line breaks.
   - Runs `html.unescape()` to decode entities and normalizes unicode whitespace (`\xa0` $\rightarrow$ `' '`).
3. **`scratch_bridge.py`**:
   - Manages scratch files in `.worksisyphus/scratch/`.
   - Saves verbatim JD text to `.worksisyphus/scratch/current_jd.txt` so agents and downstream commands inspect and read from disk without shell buffer limitations.
4. **`etl_compiler.py` (`JobTransformerPort`)**:
   - Transforms structured JSON or pre-cleaned text into `JobPosting`.
   - Extracts and normalizes screening questions, preserving prompt text and option dropdowns.
   - Fails closed if `company`, `role`, or `jd_text` are missing or empty.

### 3.4 Inbound CLI Commands (`src/worksisyphus/adapters/inbound/cli/handlers/ingest.py`)

The new `worksisyphus ingest` command group supports two modular actions:

```bash
# 1. Fetch raw URL, pre-clean, and write verbatim text to scratch
uv run worksisyphus ingest fetch <url> [--output <file>]

# 2. Compile scratch file or JSON into validated JobPosting
uv run worksisyphus ingest compile --file <file> [--company <name>] [--role <role>]

# 3. One-shot execution (fetch -> compile -> output summary)
uv run worksisyphus ingest <url> [--json]
```

Example Output of `worksisyphus ingest <url>`:
```text
Company:   Stripe
Role:      Software Engineer (Infrastructure)
Location:  Seattle, WA / Remote
Source:    greenhouse (https://boards.greenhouse.io/stripe/jobs/12345)
JD Length: 1,280 words (saved to .worksisyphus/scratch/current_jd.txt)
Questions: 3 screening questions extracted
  1. [select] "Will you now or in the future require sponsorship?" (required)
  2. [text]   "LinkedIn Profile" (optional)
  3. [text]   "GitHub Profile" (optional)
```

---

## 4. Alternatives Considered & Trade-offs

| Alternative | Pros | Cons | Decision |
|---|---|---|---|
| **Headless Browser (Playwright / Selenium)** | Handles dynamic JavaScript SPAs. | Heavy binary download (~200MB); slow startup (2-5s); violates lightweight repository footprint. | **Rejected**: Standard library `urllib` + public ATS APIs cover 95%+ of tech job boards. |
| **Echoing Full JD Text Through LLM Prompt** | Agent can reformat text. | High token cost; risk of lossy paraphrasing/summarization; bash escaping breakage on huge strings. | **Rejected**: File-based scratch bridge guarantees 100% verbatim accuracy with zero token waste. |
| **Monolithic Ingestion + Direct Apply** | Single command implementation. | Tightly couples network ingestion with LaTeX resume compilation; violates single responsibility. | **Rejected**: Decoupling ingestion (SPEC-010) from pipeline routing (SPEC-011) ensures modularity. |

---

## 5. Verification & Testing Plan

1. **Frozen Fixture Tests**:
   - `tests/fixtures/postings/` containing recorded real-world payloads:
     - `greenhouse_stripe.json`
     - `lever_palantir.json`
     - `ashby_linear.json`
     - `custom_html_posting.html`
2. **Offline Unit & Integration Suite**:
   - `test_http_fetcher.py`: Verifies browser headers, redirect following, and timeout handling with mock HTTP responses.
   - `test_pre_cleaner.py`: Verifies HTML tag stripping, newline preservation, and unicode entity decoding.
   - `test_etl_compiler.py`: Verifies exact extraction of company, role, verbatim JD, and screening questions from fixtures.
   - `test_cli_ingest.py`: Verifies `ingest fetch`, `ingest compile`, and one-shot `ingest <url>` with mock adapters.
3. **Quality Gates**:
   - `uv run python -m pytest tests/ -q` passes 100% offline.
   - `uv run ruff check .` and `uv run mypy src/ tests/` pass with zero errors.

---

## 6. Migration, Compatibility & Rollout

- **Zero Impact on Existing Commands**: `worksisyphus apply`, `tailor`, `status`, and `compile` remain 100% unchanged.
- **Gitignore Safety**: The scratch directory `.worksisyphus/scratch/` is added to `.gitignore` so temporary raw JD files are never tracked in version control.
- **Paves the Way for SPEC-011**: Provides the authoritative intake engine that SPEC-011 will connect to the Lead Vault and `apply --url`.
