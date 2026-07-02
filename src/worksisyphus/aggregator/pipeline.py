from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from worksisyphus.aggregator.config import JOBRIGHT_2026_SE_NEW_GRAD, GitHubReadmeSource
from worksisyphus.aggregator.github_source import fetch_readme, resolve_branch_head
from worksisyphus.aggregator.jobright_parser import parse_jobright_readme
from worksisyphus.aggregator.storage import (
    ensure_layout,
    latest_json_path,
    latest_jsonl_path,
    load_state,
    read_snapshot,
    save_snapshot,
    write_json,
    write_jsonl,
    write_state,
)


@dataclass(frozen=True)
class PollResult:
    source: str
    commit: str
    observed_at: str
    total_listings: int
    new_count: int
    removed_count: int
    unchanged_commit: bool
    latest_json: Path
    latest_jsonl: Path
    run_summary: Path
    state_file: Path


def poll_once(
    *,
    data_dir: Path,
    source: GitHubReadmeSource = JOBRIGHT_2026_SE_NEW_GRAD,
) -> PollResult:
    ensure_layout(data_dir)
    observed_at = datetime.now(timezone.utc).isoformat()
    previous_state = load_state(data_dir, source)

    commit_sha = resolve_branch_head(source)
    readme = read_snapshot(data_dir, source, commit_sha)
    if readme is None:
        readme = fetch_readme(source, commit_sha)
        snapshot = save_snapshot(data_dir, source, commit_sha, readme)
    else:
        snapshot = save_snapshot(data_dir, source, commit_sha, readme)

    records = parse_jobright_readme(readme, source=source, commit_sha=commit_sha)
    current_keys = {record["key"] for record in records}
    previous_keys = set((previous_state or {}).get("known_listing_keys", []))
    new_keys = sorted(current_keys - previous_keys)
    removed_keys = sorted(previous_keys - current_keys)

    latest_json = latest_json_path(data_dir, source)
    latest_jsonl = latest_jsonl_path(data_dir, source)
    write_json(
        latest_json,
        {
            "source": _source_payload(source),
            "observed_at": observed_at,
            "commit": commit_sha,
            "total_listings": len(records),
            "records": records,
        },
    )
    write_jsonl(latest_jsonl, records)

    run_payload: dict[str, Any] = {
        "source": _source_payload(source),
        "observed_at": observed_at,
        "commit": commit_sha,
        "snapshot": str(snapshot),
        "latest_json": str(latest_json),
        "latest_jsonl": str(latest_jsonl),
        "total_listings": len(records),
        "new_count": len(new_keys),
        "removed_count": len(removed_keys),
        "new_keys": new_keys,
        "removed_keys": removed_keys,
        "unchanged_commit": bool(
            previous_state and previous_state.get("last_commit") == commit_sha
        ),
    }
    run_summary = _run_summary_path(data_dir, source, observed_at, commit_sha)
    write_json(run_summary, run_payload)

    state_file = write_state(
        data_dir,
        source,
        {
            "source": _source_payload(source),
            "last_polled_at": observed_at,
            "last_commit": commit_sha,
            "known_listing_keys": sorted(current_keys),
            "last_snapshot": str(snapshot),
            "latest_json": str(latest_json),
            "latest_jsonl": str(latest_jsonl),
            "last_run_summary": str(run_summary),
        },
    )

    return PollResult(
        source=source.slug,
        commit=commit_sha,
        observed_at=observed_at,
        total_listings=len(records),
        new_count=len(new_keys),
        removed_count=len(removed_keys),
        unchanged_commit=run_payload["unchanged_commit"],
        latest_json=latest_json,
        latest_jsonl=latest_jsonl,
        run_summary=run_summary,
        state_file=state_file,
    )


def _source_payload(source: GitHubReadmeSource) -> dict[str, str]:
    return {
        "name": source.slug,
        "repo": source.repo_url,
        "branch": source.branch,
        "path": source.path,
    }


def _run_summary_path(
    data_dir: Path,
    source: GitHubReadmeSource,
    observed_at: str,
    commit_sha: str,
) -> Path:
    timestamp = (
        observed_at.replace("+00:00", "Z")
        .replace(":", "")
        .replace("-", "")
        .replace(".", "")
    )
    short_sha = commit_sha[:12]
    return data_dir / "runs" / source.slug / f"{timestamp}-{short_sha}.json"
