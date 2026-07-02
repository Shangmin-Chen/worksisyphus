from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_catalog(db_path: Path) -> None:
    with connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                canonical_id TEXT PRIMARY KEY,
                dedupe_key TEXT NOT NULL,
                company_name TEXT,
                title TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                latest_source_url TEXT,
                application_status TEXT NOT NULL DEFAULT 'new',
                applied_at TEXT,
                ignored_at TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_dedupe_key
            ON jobs(dedupe_key);

            CREATE INDEX IF NOT EXISTS idx_jobs_application_status
            ON jobs(application_status);

            CREATE TABLE IF NOT EXISTS job_sources (
                source_name TEXT NOT NULL,
                source_key TEXT NOT NULL,
                canonical_id TEXT NOT NULL,
                source_listing_url TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                PRIMARY KEY (source_name, source_key),
                FOREIGN KEY (canonical_id) REFERENCES jobs(canonical_id)
            );

            CREATE TABLE IF NOT EXISTS job_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                canonical_id TEXT NOT NULL,
                dedupe_key TEXT NOT NULL,
                source_name TEXT,
                source_key TEXT,
                observed_at TEXT NOT NULL,
                normalized_json TEXT NOT NULL,
                FOREIGN KEY (canonical_id) REFERENCES jobs(canonical_id)
            );

            CREATE INDEX IF NOT EXISTS idx_job_observations_run_id
            ON job_observations(run_id);

            CREATE TABLE IF NOT EXISTS enrichments (
                canonical_id TEXT PRIMARY KEY,
                enriched_at TEXT NOT NULL,
                source_url TEXT,
                status TEXT NOT NULL,
                http_status INTEGER,
                content_hash TEXT,
                enriched_json TEXT,
                error TEXT,
                FOREIGN KEY (canonical_id) REFERENCES jobs(canonical_id)
            );

            CREATE TABLE IF NOT EXISTS application_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_time TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (canonical_id) REFERENCES jobs(canonical_id)
            );
            """
        )


def upsert_normalized_jobs(
    db_path: Path,
    *,
    jobs: list[dict],
    observed_at: str,
    run_id: str,
) -> None:
    init_catalog(db_path)
    with connect(db_path) as connection:
        for job in jobs:
            identity = job.get("identity", {})
            company = job.get("company", {})
            role = job.get("role", {})
            application = job.get("application", {})
            source = job.get("source", {})

            canonical_id = identity["canonical_id"]
            dedupe_key = identity["dedupe_key"]
            source_name = source.get("name") or "unknown"
            source_key = (
                identity.get("source_job_id")
                or identity.get("source_record_key")
                or canonical_id
            )
            source_listing_url = application.get("source_listing_url")

            connection.execute(
                """
                INSERT INTO jobs (
                    canonical_id,
                    dedupe_key,
                    company_name,
                    title,
                    first_seen_at,
                    last_seen_at,
                    latest_source_url,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_id) DO UPDATE SET
                    dedupe_key = excluded.dedupe_key,
                    company_name = excluded.company_name,
                    title = excluded.title,
                    last_seen_at = excluded.last_seen_at,
                    latest_source_url = excluded.latest_source_url,
                    updated_at = excluded.updated_at
                """,
                (
                    canonical_id,
                    dedupe_key,
                    company.get("name"),
                    role.get("title"),
                    observed_at,
                    observed_at,
                    source_listing_url,
                    observed_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO job_sources (
                    source_name,
                    source_key,
                    canonical_id,
                    source_listing_url,
                    first_seen_at,
                    last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_name, source_key) DO UPDATE SET
                    canonical_id = excluded.canonical_id,
                    source_listing_url = excluded.source_listing_url,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    source_name,
                    source_key,
                    canonical_id,
                    source_listing_url,
                    observed_at,
                    observed_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO job_observations (
                    run_id,
                    canonical_id,
                    dedupe_key,
                    source_name,
                    source_key,
                    observed_at,
                    normalized_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    canonical_id,
                    dedupe_key,
                    source_name,
                    source_key,
                    observed_at,
                    json.dumps(job, sort_keys=True),
                ),
            )


def enrichment_exists(db_path: Path, canonical_id: str) -> bool:
    init_catalog(db_path)
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT 1 FROM enrichments WHERE canonical_id = ?",
            (canonical_id,),
        ).fetchone()
    return row is not None


def upsert_enrichment(
    db_path: Path,
    *,
    canonical_id: str,
    enriched_at: str,
    source_url: str | None,
    status: str,
    http_status: int | None,
    content_hash: str | None,
    enriched: dict[str, Any] | None,
    error: str | None,
) -> None:
    init_catalog(db_path)
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO enrichments (
                canonical_id,
                enriched_at,
                source_url,
                status,
                http_status,
                content_hash,
                enriched_json,
                error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(canonical_id) DO UPDATE SET
                enriched_at = excluded.enriched_at,
                source_url = excluded.source_url,
                status = excluded.status,
                http_status = excluded.http_status,
                content_hash = excluded.content_hash,
                enriched_json = excluded.enriched_json,
                error = excluded.error
            """,
            (
                canonical_id,
                enriched_at,
                source_url,
                status,
                http_status,
                content_hash,
                json.dumps(enriched, sort_keys=True) if enriched else None,
                error,
            ),
        )


def mark_applied(
    db_path: Path,
    *,
    canonical_id: str,
    applied_at: str,
    notes: str | None = None,
) -> None:
    init_catalog(db_path)
    with connect(db_path) as connection:
        connection.execute(
            """
            UPDATE jobs
            SET application_status = 'applied',
                applied_at = ?,
                updated_at = ?
            WHERE canonical_id = ?
            """,
            (applied_at, applied_at, canonical_id),
        )
        connection.execute(
            """
            INSERT INTO application_events (
                canonical_id,
                event_type,
                event_time,
                notes
            )
            VALUES (?, 'applied', ?, ?)
            """,
            (canonical_id, applied_at, notes),
        )


def application_status(db_path: Path, canonical_id: str) -> str | None:
    init_catalog(db_path)
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT application_status FROM jobs WHERE canonical_id = ?",
            (canonical_id,),
        ).fetchone()
    if row is None:
        return None
    return str(row["application_status"])
