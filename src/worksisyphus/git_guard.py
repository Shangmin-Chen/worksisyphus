"""Git repository state and freshness verification for Turso cloud synchronization."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Log = Callable[[str], None]


def _silent(_: str) -> None:
    pass


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
    allow_any_branch: bool = False,
    check_upstream: bool = True,
    fetch_timeout: float = 2.0,
    runner: Callable[..., Any] = subprocess.run,
) -> GitFreshnessResult:
    """Verify that the repository is on target_branch and up-to-date with remote before syncing to Turso.

    Returns a GitFreshnessResult indicating whether cloud synchronization is safe.
    """
    # 1. Verify this is a git repository
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

    # 2. Check current branch
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
        if not allow_any_branch:
            return GitFreshnessResult(
                allowed=False,
                branch="(detached HEAD)",
                reason="Detached HEAD state; cloud sync is restricted to the main branch.",
            )
    elif current_branch != target_branch and not allow_any_branch:
        return GitFreshnessResult(
            allowed=False,
            branch=current_branch,
            reason=(
                f"Current branch is '{current_branch}', not '{target_branch}'. "
                f"Cloud sync is restricted to '{target_branch}' to prevent overwriting cloud state from feature branches."
            ),
        )

    # 3. Check upstream freshness (if requested)
    if check_upstream:
        # Best-effort background fetch of remote target branch with tight timeout
        try:
            runner(
                ["git", "-C", str(repo_dir), "fetch", "origin", target_branch],
                capture_output=True,
                text=True,
                timeout=fetch_timeout,
            )
        except Exception:
            # Network failure or timeout; continue with local cached remote ref
            pass

        # Check commits behind origin/target_branch
        try:
            res = runner(
                ["git", "-C", str(repo_dir), "rev-list", "--count", f"HEAD..origin/{target_branch}"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if res.returncode == 0:
                behind = int(res.stdout.strip() or "0")
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
        except Exception:
            # If origin ref does not exist (e.g. fresh clone with no remotes), proceed
            pass

    return GitFreshnessResult(allowed=True, branch=current_branch, behind_count=0)
