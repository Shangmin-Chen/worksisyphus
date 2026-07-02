# WorkSisyphus

Phase 1 is a narrow job-listing aggregator. It listens to one source only:

- `jobright-ai/2026-Software-Engineer-New-Grad`

The aggregator fetches the source README from GitHub, stores immutable raw snapshots by commit SHA, extracts the README table into source-shaped records, and keeps local state so subsequent polls can report newly seen and removed listings.

Phase 2 normalizes the latest phase-1 artifact into the canonical job shape that later scoring, tailoring, and application workers can consume.

## Run

```bash
uv run worksisyphus-aggregate poll
uv run worksisyphus-normalize run
uv run worksisyphus-enrich run
```

By default, output is written under `.worksisyphus/`.

Useful options:

```bash
uv run worksisyphus-aggregate poll --data-dir .worksisyphus/aggregator
uv run worksisyphus-aggregate watch --interval 300
uv run worksisyphus-normalize run --aggregator-dir .worksisyphus/aggregator --output-dir .worksisyphus/normalizer
uv run worksisyphus-enrich run --limit 25
uv run worksisyphus-enrich run --limit 0
uv run worksisyphus-catalog mark-applied <canonical_id>
```

## Development

```bash
uv sync
uv run python -m unittest discover -s tests
```

## Phase 1 Output

The collector writes:

- `raw/<source>/<commit>/README.md`: raw source snapshot
- `runs/<timestamp>-<commit>.json`: poll summary, including new and removed listing keys
- `latest/<source>.json`: current extracted listings
- `latest/<source>.jsonl`: current extracted listings as JSON lines
- `state/<source>.json`: local listener state

This is intentionally pre-normalization. Phase 2 can consume the latest JSON/JSONL files and transform them into the canonical job model.

## Phase 2 Output

The normalizer writes:

- `latest/jobs.json`: canonical job records with metadata
- `latest/jobs.jsonl`: canonical job records as JSON lines
- `runs/<timestamp>.json`: normalization run summary

Normalized records include stable identity keys, company, role, location, workplace type, inferred posted date, application URLs, source metadata, and quality warnings.

## Phase 3 Output

Phase 3 enriches normalized jobs by fetching each listing detail page and extracting embedded structured data. For Jobright detail pages, this currently provides full job description text, responsibilities, skills, salary, seniority, location, active/deleted status, company metadata, and hiring signals such as H1B sponsorship or clearance requirements.

The enricher writes:

- `.worksisyphus/catalog.sqlite3`: persistent source of truth for latest jobs, dedupe keys, enrichments, and application status
- `enricher/latest/enriched_jobs.json`: enriched records from the latest enrichment run
- `enricher/latest/enriched_jobs.jsonl`: enriched records from the latest enrichment run as JSON lines
- `enricher/runs/<timestamp>.json`: enrichment run summary

JSON files are artifacts for inspection and handoff. SQLite is the durable state store. Use it to answer "what is latest?", preserve manually applied status, and avoid re-enriching jobs that were already processed.
