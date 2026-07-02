from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import time

from worksisyphus.catalog.db import (
    enrichment_exists,
    upsert_enrichment,
    upsert_normalized_jobs,
)
from worksisyphus.enricher.extract import extract_jobright_detail
from worksisyphus.enricher.fetch import fetch_html
from worksisyphus.enricher.schema import SCHEMA_VERSION
from worksisyphus.normalizer.storage import read_json, write_json, write_jsonl


@dataclass(frozen=True)
class EnrichResult:
    observed_at: str
    input_file: Path
    db_path: Path
    attempted_count: int
    enriched_count: int
    skipped_count: int
    failed_count: int
    latest_json: Path
    latest_jsonl: Path
    run_summary: Path


def enrich_latest(
    *,
    normalizer_dir: Path,
    output_dir: Path,
    db_path: Path,
    limit: int | None,
    refresh: bool = False,
    delay_seconds: float = 0.25,
) -> EnrichResult:
    input_file = normalizer_dir / "latest" / "jobs.json"
    if not input_file.exists():
        raise FileNotFoundError(
            f"missing normalizer input {input_file}; run phase 2 first"
        )

    payload = read_json(input_file)
    observed_at = datetime.now(timezone.utc).isoformat()
    run_id = _run_id(observed_at)
    jobs = payload.get("jobs", [])
    upsert_normalized_jobs(
        db_path,
        jobs=jobs,
        observed_at=payload.get("normalized_at") or observed_at,
        run_id=run_id,
    )

    candidates = _select_candidates(jobs, db_path=db_path, limit=limit, refresh=refresh)
    enriched_records: list[dict] = []
    failures: list[dict] = []

    for index, job in enumerate(candidates):
        canonical_id = job["identity"]["canonical_id"]
        source_url = job.get("application", {}).get("source_listing_url")
        if not source_url:
            failures.append(
                {
                    "canonical_id": canonical_id,
                    "source_url": None,
                    "error": "missing_source_listing_url",
                }
            )
            upsert_enrichment(
                db_path,
                canonical_id=canonical_id,
                enriched_at=observed_at,
                source_url=None,
                status="failed",
                http_status=None,
                content_hash=None,
                enriched=None,
                error="missing_source_listing_url",
            )
            continue

        fetch_result = fetch_html(source_url)
        if fetch_result.error or not fetch_result.body:
            error = fetch_result.error or "empty_response_body"
            failures.append(
                {
                    "canonical_id": canonical_id,
                    "source_url": source_url,
                    "error": error,
                }
            )
            upsert_enrichment(
                db_path,
                canonical_id=canonical_id,
                enriched_at=observed_at,
                source_url=source_url,
                status="failed",
                http_status=fetch_result.status_code,
                content_hash=None,
                enriched=None,
                error=error,
            )
        else:
            extracted = extract_jobright_detail(
                html=fetch_result.body,
                source_url=source_url,
                normalized_job=job,
                fetched_at=observed_at,
                final_url=fetch_result.url,
            )
            enriched_records.append(extracted.record)
            upsert_enrichment(
                db_path,
                canonical_id=canonical_id,
                enriched_at=observed_at,
                source_url=source_url,
                status=extracted.status,
                http_status=fetch_result.status_code,
                content_hash=extracted.content_hash,
                enriched=extracted.record,
                error=None,
            )

        if delay_seconds > 0 and index + 1 < len(candidates):
            time.sleep(delay_seconds)

    latest_json = output_dir / "latest" / "enriched_jobs.json"
    latest_jsonl = output_dir / "latest" / "enriched_jobs.jsonl"
    output_payload = {
        "schema_version": SCHEMA_VERSION,
        "enriched_at": observed_at,
        "input_file": str(input_file),
        "db_path": str(db_path),
        "total_normalized_jobs": len(jobs),
        "attempted_count": len(candidates),
        "enriched_count": len(enriched_records),
        "skipped_count": max(0, len(jobs) - len(candidates)),
        "failed_count": len(failures),
        "failures": failures,
        "jobs": enriched_records,
    }
    write_json(latest_json, output_payload)
    write_jsonl(latest_jsonl, enriched_records)

    run_summary = output_dir / "runs" / f"{run_id}.json"
    write_json(
        run_summary,
        {
            "schema_version": SCHEMA_VERSION,
            "enriched_at": observed_at,
            "input_file": str(input_file),
            "db_path": str(db_path),
            "total_normalized_jobs": len(jobs),
            "attempted_count": len(candidates),
            "enriched_count": len(enriched_records),
            "skipped_count": max(0, len(jobs) - len(candidates)),
            "failed_count": len(failures),
            "failures": failures,
            "refresh": refresh,
            "limit": limit,
        },
    )

    return EnrichResult(
        observed_at=observed_at,
        input_file=input_file,
        db_path=db_path,
        attempted_count=len(candidates),
        enriched_count=len(enriched_records),
        skipped_count=max(0, len(jobs) - len(candidates)),
        failed_count=len(failures),
        latest_json=latest_json,
        latest_jsonl=latest_jsonl,
        run_summary=run_summary,
    )


def _select_candidates(
    jobs: list[dict],
    *,
    db_path: Path,
    limit: int | None,
    refresh: bool,
) -> list[dict]:
    candidates: list[dict] = []
    for job in jobs:
        canonical_id = job["identity"]["canonical_id"]
        if not refresh and enrichment_exists(db_path, canonical_id):
            continue
        candidates.append(job)
        if limit is not None and len(candidates) >= limit:
            break
    return candidates


def _run_id(observed_at: str) -> str:
    return (
        observed_at.replace("+00:00", "Z")
        .replace(":", "")
        .replace("-", "")
        .replace(".", "")
    )
