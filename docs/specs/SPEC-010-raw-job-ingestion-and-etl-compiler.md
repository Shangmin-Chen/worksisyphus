# SPEC-010: Universal Job Ingestion, Agent Bridge & Dual-Venue Loading

| Field | Value |
|---|---|
| **Spec ID** | `SPEC-010` |
| **Title** | Universal Job Ingestion, Agent Bridge & Dual-Venue Loading |
| **Status** | `Accepted` |
| **Author** | Simon Chen & Antigravity |
| **Created** | 2026-09-23 |
| **Updated** | 2026-09-23 |
| **Supersedes** | None |
| **Superseded By** | None |
| **Related Issues/PRs** | #98 |

---

## 1. Context & Problem Statement

Historically, `worksisyphus apply` has been a passive resume compiler requiring operators and agents to manually copy-paste multi-paragraph job descriptions into the CLI via stdin (`--jd -`). 

Early architectural drafts attempted to solve automated intake by reverse-engineering vendor-specific ATS endpoints (Greenhouse, Lever, Ashby JSON APIs) and writing fragile AST heuristics to parse form fields. This was rejected as over-engineered slop: vendor APIs frequently change schemas, fail on non-standard portals (Workday, Taleo, custom career sites), and ignore the natural intelligence of the autonomous agent operating the system.

Instead, the modern intake architecture is an **agent-native dumb pipe**:
1. **Universal Ingest**: A lightweight HTTP fetcher and HTML pre-cleaner that fetches *any* job URL, strips boilerplate markup, and writes clean text to scratch disk.
2. **Agent in the Middle**: The autonomous agent (Gemini, Claude, Antigravity) reads the clean text, effortlessly extracting company, role, requirements, and screening questions.
3. **Dual-Venue Loading**:
   - **Venue 1 (Lead Vault)**: `worksisyphus track` records the opportunity in `leads/<stem>/` (`meta.json`, `jd.txt`, `questions.json`) for pipeline tracking and interview prep without compiling a resume.
   - **Venue 2 (Resume Generation)**: `worksisyphus apply --url <url>` or `worksisyphus apply --lead <stem>` compiles a tailored, 1-page PDF directly into `applications/<stem>/`.

---

## 2. Invariants & Bounded Rules

1. **Universal Dumb Pipe**: The ingestion layer contains zero vendor-specific scraping heuristics, zero ATS API sniffing, and zero fragile DOM element selectors. It works identically for Greenhouse, Workday, Lever, Ashby, or a company blog post.
2. **Agent-Mediated Extraction**: Identifying the hiring company, role title, and pre-screening questions is performed by the LLM agent reading the pre-cleaned text, not by brittle regexes or AST parsers.
3. **Verbatim Text Preservation**: The pre-cleaner strips markup noise (`<script>`, `<style>`, `<nav>`, `<footer>`) but preserves the exact wording, bullets, and structural paragraphs of the job description.
4. **File-Based Scratch Bridge**: Giant multi-paragraph JD texts flow from network to disk (`.worksisyphus/scratch/current_jd.txt`) and disk to compiler. They are never passed as giant inline shell arguments.
5. **Venue 1 Isolation (The Lead Vault)**: Tracked opportunities live in `leads/<YYYY-MM-DD>_<stem>/`. They do not require a compiled PDF, preserving the invariant in `tests/test_consistency.py` that `applications/` only holds delivered, employer-facing resumes.
6. **Promotion from Lead to Application**: A tracked lead can be promoted to a full application via `worksisyphus apply --lead <stem>`. This compiles the resume, copies screening questions, and updates the lead status to `"applied"`.
7. **Offline Testability**: All tests execute 100% offline with zero internet access, zero external API keys, and sub-second execution speed.

---

## 3. Architecture & Data Flow

```
   [ External Job URL (Any Web Site) ]
                 │
                 ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ 1. Universal Fetcher (adapters/outbound/ingestion/http)     │
   │ • stdlib urllib with browser User-Agent headers             │
   │ • Redirect following, SSL handling, explicit 10s timeout    │
   └──────────────────────────────┬──────────────────────────────┘
                                  │ Raw HTML
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ 2. Pre-Cleaner & Scratch Bridge                             │
   │ • Strips <script>, <style>, <nav>, <footer>, <header>       │
   │ • Decodes entities (&amp; -> &, &nbsp; -> ' ')              │
   │ • Writes verbatim text to `.worksisyphus/scratch/current_jd`│
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ 3. THE AGENT LAYER (Autonomous AI Operator)                 │
   │ • Inspects `.worksisyphus/scratch/current_jd.txt`           │
   │ • Identifies: Company, Role, Location, Screening Questions  │
   │ • Chooses Venue 1 (Track Lead) or Venue 2 (Apply Resume)    │
   └──────────────┬──────────────────────────────┬───────────────┘
                  │                              │
                  ▼                              ▼
      [ Venue 1: Lead Vault ]        [ Venue 2: Resume Compiler ]
        `worksisyphus track`            `worksisyphus apply`
                  │                              │
                  ▼                              ▼
       `leads/<YYYY-MM-DD>_<stem>/`    `applications/<YYYY-MM-DD>_<stem>/`
       ├── meta.json                   ├── meta.json
       ├── jd.txt                      ├── jd.txt
       └── questions.json (optional)   ├── plan.json
                                       ├── Simon_Chen_Resume.pdf
                                       └── questions.json (if promoted)
```

---

## 4. Component Design

### 4.1 Ingestion Ports & Adapters

- **`HttpRawFetcher` (`src/worksisyphus/adapters/outbound/ingestion/http_fetcher.py`)**:
  - Implements `RawFetcherPort`.
  - Performs standard HTTP GET requests using `urllib.request`.
  - Uses browser headers to avoid trivial blocking.
  - Decodes response content using declared charset or UTF-8.
- **`PreCleaner` (`src/worksisyphus/adapters/outbound/ingestion/pre_cleaner.py`)**:
  - Uses stdlib `html.parser.HTMLParser`.
  - Strips `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<iframe>`.
  - Normalizes line breaks for lists and paragraphs.
  - Unescapes HTML entities.
- **`ScratchBridge` (`src/worksisyphus/adapters/outbound/ingestion/scratch_bridge.py`)**:
  - Saves verbatim text to `.worksisyphus/scratch/current_jd.txt`.

### 4.2 Core Tracker Service (`src/worksisyphus/core/use_cases/tracker.py`)

- `track_lead(company, jd_text, role, url, questions, leads_dir, when)`:
  - Generates deterministic `<YYYY-MM-DD>_<comp_slug>_<role_slug>` folder stem.
  - Handles same-day collisions by appending `_2`, `_3`.
  - Writes `meta.json`, `jd.txt`, and optional `questions.json`.
- `list_leads(leads_dir)`:
  - Lists tracked leads in date-descending order.
- `get_lead(stem_or_name, leads_dir)`:
  - Retrieves folder path, metadata, and verbatim JD.
- `update_lead_status(stem_or_name, status, leads_dir)`:
  - Updates status in `meta.json` (e.g. `"tracked"` $\rightarrow$ `"applied"`).

### 4.3 CLI Commands

1. **Ingest (Dumb Pipe)**:
   ```bash
   uv run worksisyphus ingest <url> [--output <file>]
   ```
2. **Venue 1: Track Lead**:
   ```bash
   uv run worksisyphus track --company <Name> [--role <Role>] [--url <URL>] [--jd <file|->] [--questions <file>]
   uv run worksisyphus leads
   ```
3. **Venue 2: Resume Compiler**:
   ```bash
   # Direct URL apply (fetches, cleans, and compiles 1-page resume)
   uv run worksisyphus apply --company <Name> --url <URL> [--role <Role>]

   # Lead promotion apply (reads from leads/ vault, compiles resume, marks applied)
   uv run worksisyphus apply --lead <stem>
   ```

---

## 5. Verification & Testing

- `tests/test_pre_cleaner.py`: Verifies noise removal, structural line breaks, entity unescaping.
- `tests/test_scratch_bridge.py`: Verifies scratch read/write operations and payload persistence.
- `tests/test_http_fetcher.py`: Verifies HTTP fetch, error handling (404, timeouts, invalid protocols) with mock transport.
- `tests/test_cli_ingest.py`: Verifies `worksisyphus ingest <url>` and custom output options.
- `tests/test_tracker.py`: Verifies lead creation, collision handling, listing, status updates, and CLI `track`/`leads`.
- `tests/test_apply_venues.py`: Verifies `apply --url <url>` and `apply --lead <stem>` promotion flow.

---

## 6. Migration & Rollout

- Added `/leads/` to `.gitignore` to protect operator's private job lead repository.
- Standard resume generation (`worksisyphus apply --company <C> --jd <file|->`) remains 100% backward compatible.
- All quality gates (no GPA, banned content, ATS check, 1-page trim) remain strictly enforced.
