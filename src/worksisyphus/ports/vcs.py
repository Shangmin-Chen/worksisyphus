"""VCS Port: Abstract boundary protocol for Git repository state and freshness verification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class GitFreshnessResult:
    """Outcome of checking git repository state before cloud operations."""

    allowed: bool
    branch: str = ""
    behind_count: int = 0
    reason: str = ""


@runtime_checkable
class GitGuardPort(Protocol):
    """Port interface for verifying git branch and synchronization freshness."""

    def check_git_freshness(
        self,
        repo_dir: Path = Path("."),
        target_branch: str = "main",
        allow_branch: bool = False,
        fetch_timeout: float = 2.0,
    ) -> GitFreshnessResult:
        """Check whether local git state permits synchronization with remote cloud."""
        ...
