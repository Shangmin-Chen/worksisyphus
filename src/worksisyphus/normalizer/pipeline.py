from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from worksisyphus.aggregator.config import JOBRIGHT_2026_SE_NEW_GRAD
from worksisyphus.normalizer.normalize import normalize_payload
from worksisyphus.normalizer.schema import SCHEMA_VERSION
from worksisyphus.normalizer.storage import read_json, write_json, write_jsonl


@dataclass(frozen=True)
class NormalizeResult:
    source: str
    observed_at: str
    input_file: Path
    total_jobs: int
    needs_review_count: int
    latest_json: Path
    latest_jsonl: Path
    run_summary: Path


def normalize_latest(
    *,
    aggregator_dir: Path,
    output_dir: Path,
    source_slug: str = JOBRIGHT_2026_SE_NEW_GRAD.slug,
) -> NormalizeResult:
    input_file = aggregator_dir / "latest" / f"{source_slug}.json"
    if not input_file.exists():
        raise FileNotFoundError(
            f"missing aggregator input {input_file}; run the phase 1 poll first"
        )

    payload = read_json(input_file)
    observed_at = datetime.now(timezone.utc).isoformat()
    jobs = normalize_payload(payload)
    needs_review_count = sum(1 for job in jobs if job["quality"]["needs_review"])

    latest_json = output_dir / "latest" / "jobs.json"
    latest_jsonl = output_dir / "latest" / "jobs.jsonl"
    output_payload = {
        "schema_version": SCHEMA_VERSION,
        "source": payload.get("source"),
        "normalized_at": observed_at,
        "input_file": str(input_file),
        "input_observed_at": payload.get("observed_at"),
        "input_commit": payload.get("commit"),
        "total_jobs": len(jobs),
        "needs_review_count": needs_review_count,
        "jobs": jobs,
    }
    write_json(latest_json, output_payload)
    write_jsonl(latest_jsonl, jobs)

    run_summary = _run_summary_path(output_dir, observed_at)
    write_json(
        run_summary,
        {
            "schema_version": SCHEMA_VERSION,
            "source": payload.get("source"),
            "normalized_at": observed_at,
            "input_file": str(input_file),
            "latest_json": str(latest_json),
            "latest_jsonl": str(latest_jsonl),
            "total_jobs": len(jobs),
            "needs_review_count": needs_review_count,
            "input_observed_at": payload.get("observed_at"),
            "input_commit": payload.get("commit"),
        },
    )

    return NormalizeResult(
        source=source_slug,
        observed_at=observed_at,
        input_file=input_file,
        total_jobs=len(jobs),
        needs_review_count=needs_review_count,
        latest_json=latest_json,
        latest_jsonl=latest_jsonl,
        run_summary=run_summary,
    )


def _run_summary_path(output_dir: Path, observed_at: str) -> Path:
    timestamp = (
        observed_at.replace("+00:00", "Z")
        .replace(":", "")
        .replace("-", "")
        .replace(".", "")
    )
    return output_dir / "runs" / f"{timestamp}.json"
