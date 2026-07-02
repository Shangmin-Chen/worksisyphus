from __future__ import annotations

import subprocess
import urllib.request

from worksisyphus.aggregator.config import GitHubReadmeSource


class SourceFetchError(RuntimeError):
    """Raised when a configured GitHub README source cannot be fetched."""


def resolve_branch_head(source: GitHubReadmeSource) -> str:
    ref = f"refs/heads/{source.branch}"
    completed = subprocess.run(
        ["git", "ls-remote", source.clone_url, ref],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SourceFetchError(f"git ls-remote failed for {source.repo_url}: {detail}")

    line = completed.stdout.strip()
    if not line:
        raise SourceFetchError(
            f"branch {source.branch!r} was not found for {source.repo_url}"
        )

    commit_sha = line.split()[0]
    if len(commit_sha) != 40:
        raise SourceFetchError(f"unexpected commit SHA from git ls-remote: {line!r}")
    return commit_sha


def fetch_readme(source: GitHubReadmeSource, commit_sha: str) -> str:
    request = urllib.request.Request(
        source.raw_url(commit_sha),
        headers={
            "Accept": "text/plain",
            "User-Agent": "worksisyphus-phase1-aggregator/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except OSError as exc:
        raise SourceFetchError(
            f"failed to fetch {source.path} at {commit_sha} from {source.repo_url}: {exc}"
        ) from exc
