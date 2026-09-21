"""Backward-compatibility facade for plan parsing."""

from __future__ import annotations

from .core.domain.models import PlanError
from .core.domain.plan import parse_plan

__all__ = ["PlanError", "parse_plan"]
