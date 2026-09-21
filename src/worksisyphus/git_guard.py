"""Backward-compatibility facade for VCS git freshness check."""

from __future__ import annotations

import sys

from .adapters.outbound.git import subprocess_guard as _module
from .adapters.outbound.git.subprocess_guard import (
    SubprocessGitGuard,
    check_git_freshness_for_sync,
)
from .ports.vcs import GitFreshnessResult, GitGuardPort

sys.modules[__name__] = _module

__all__ = [
    "GitFreshnessResult",
    "GitGuardPort",
    "SubprocessGitGuard",
    "check_git_freshness_for_sync",
]
