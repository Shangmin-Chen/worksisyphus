"""Backward-compatibility facade for hiring agent evaluation."""

from __future__ import annotations

import sys

from .core.use_cases import hiring_agent as _module
from .core.use_cases.hiring_agent import (
    ROLES_DIR,
    UPSTREAM_MANIFEST_PATH,
    Category,
    CategoryScore,
    Deductions,
    HackerRankHiringAgent,
    Role,
    build_evaluation_model,
    check_upstream_status,
    format_hackerrank_report,
    list_roles,
    load_role,
    synthesize_role_rubric,
)

sys.modules[__name__] = _module

__all__ = [
    "ROLES_DIR",
    "UPSTREAM_MANIFEST_PATH",
    "Category",
    "CategoryScore",
    "Deductions",
    "HackerRankHiringAgent",
    "Role",
    "build_evaluation_model",
    "check_upstream_status",
    "format_hackerrank_report",
    "list_roles",
    "load_role",
    "synthesize_role_rubric",
]
