"""Git repository state and freshness verification for Turso cloud synchronization."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GitFreshnessResult:
    """Outcome of checking git repository state before cloud operations."""

    allowed: bool
    branch: str = ""
    behind_count: int = 0
    reason: str = ""


def check_git_freshness_for_sync(
    repo_dir: Path = Path("."),
    target_branch: str = "main",
    allow_branch: bool = False,
    fetch_timeout: float = 2.0,
    runner: Callable[..., Any] = subprocess.run,
) -> GitFreshnessResult:
    """Verify that the repository is on target_branch and not behind origin/target_branch.

    Fetch is best-effort (timeout, then cached refs). A missing or unreadable
    origin/<target_branch> fails closed — pass --no-git-check to skip the gate.
    """
    try:
        res = runner(
            ["git", "-C", str(repo_dir), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if res.returncode != 0 or res.stdout.strip() != "true":
            return GitFreshnessResult(
                allowed=False,
                reason="Not inside a git work tree; cloud sync is disabled outside a git repository.",
            )
    except Exception as exc:
        return GitFreshnessResult(
            allowed=False,
            reason=f"Failed to inspect git repository: {exc}",
        )

    try:
        res = runner(
            ["git", "-C", str(repo_dir), "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        current_branch = res.stdout.strip()
    except Exception as exc:
        return GitFreshnessResult(
            allowed=False,
            reason=f"Failed to determine current git branch: {exc}",
        )

    if not current_branch:
        return GitFreshnessResult(
            allowed=False,
            branch="(detached HEAD)",
            reason="Detached HEAD state; cloud sync requires a named branch.",
        )
    if current_branch != target_branch and not allow_branch:
        return GitFreshnessResult(
            allowed=False,
            branch=current_branch,
            reason=(
                f"Current branch is '{current_branch}', not '{target_branch}'. "
                f"Cloud sync is restricted to '{target_branch}' to prevent overwriting cloud state from feature branches."
            ),
        )

    try:
        runner(
            ["git", "-C", str(repo_dir), "fetch", "origin", target_branch],
            capture_output=True,
            text=True,
            timeout=fetch_timeout,
        )
    except Exception:
        pass

    unverifiable = GitFreshnessResult(
        allowed=False,
        branch=current_branch,
        reason=(
            f"Could not verify freshness against origin/{target_branch}. "
            f"Fetch that ref, or pass --no-git-check to skip this gate."
        ),
    )
    try:
        res = runner(
            ["git", "-C", str(repo_dir), "rev-list", "--count", f"HEAD..origin/{target_branch}"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except Exception:
        return unverifiable
    if res.returncode != 0:
        return unverifiable
    try:
        behind = int(res.stdout.strip() or "0")
    except ValueError:
        return unverifiable
    if behind > 0:
        return GitFreshnessResult(
            allowed=False,
            branch=current_branch,
            behind_count=behind,
            reason=(
                f"Local branch is behind origin/{target_branch} by {behind} commit(s). "
                f"Run 'git pull' before syncing to Turso cloud."
            ),
        )
    return GitFreshnessResult(allowed=True, branch=current_branch, behind_count=0)
