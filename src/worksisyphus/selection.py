"""Backward-compatibility facade for selection models and rules."""

from __future__ import annotations

from .core.domain.models import TAILORED_NAME, Pick, Selection
from .core.domain.rules import MIN_BULLETS, full_selection, trim_step

__all__ = [
    "MIN_BULLETS",
    "TAILORED_NAME",
    "Pick",
    "Selection",
    "full_selection",
    "trim_step",
]
