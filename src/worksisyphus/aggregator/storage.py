from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from worksisyphus.aggregator.config import GitHubReadmeSource


def ensure_layout(data_dir: Path) -> None:
    for child in ("raw", "latest", "runs", "state"):
        (data_dir / child).mkdir(parents=True, exist_ok=True)


def snapshot_path(data_dir: Path, source: GitHubReadmeSource, commit_sha: str) -> Path:
    return data_dir / "raw" / source.slug / commit_sha / source.path


def save_snapshot(
    data_dir: Path,
    source: GitHubReadmeSource,
    commit_sha: str,
    content: str,
) -> Path:
    path = snapshot_path(data_dir, source, commit_sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")
    return path


def read_snapshot(data_dir: Path, source: GitHubReadmeSource, commit_sha: str) -> str | None:
    path = snapshot_path(data_dir, source, commit_sha)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def latest_json_path(data_dir: Path, source: GitHubReadmeSource) -> Path:
    return data_dir / "latest" / f"{source.slug}.json"


def latest_jsonl_path(data_dir: Path, source: GitHubReadmeSource) -> Path:
    return data_dir / "latest" / f"{source.slug}.jsonl"


def state_path(data_dir: Path, source: GitHubReadmeSource) -> Path:
    return data_dir / "state" / f"{source.slug}.json"


def load_state(data_dir: Path, source: GitHubReadmeSource) -> dict[str, Any] | None:
    path = state_path(data_dir, source)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_state(
    data_dir: Path,
    source: GitHubReadmeSource,
    payload: dict[str, Any],
) -> Path:
    path = state_path(data_dir, source)
    write_json(path, payload)
    return path
