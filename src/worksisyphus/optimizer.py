"""Backward-compatibility facade for plan knapsack optimizer."""

from __future__ import annotations

import sys

from .core.use_cases import optimizer as _module
from .core.use_cases.optimizer import (
    HEADER_LINE_COST,
    MAX_EXPERIENCE_PROJECT_LINES,
    OptimizerError,
    format_optimization_report,
    generate_candidate_plans,
    optimize_plan,
)

sys.modules[__name__] = _module

__all__ = [
    "HEADER_LINE_COST",
    "MAX_EXPERIENCE_PROJECT_LINES",
    "OptimizerError",
    "format_optimization_report",
    "generate_candidate_plans",
    "optimize_plan",
]
