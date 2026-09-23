"""Backward-compatibility facade for LaTeX resume rendering."""

from __future__ import annotations

import sys

from .core.domain.models import CompilerConfig, CourseworkMode
from .core.rendering import latex as _module
from .core.rendering.latex import (
    DEFAULT_TEMPLATE_PATH,
    SKILL_GROUP_LABELS,
    render_resume,
)

sys.modules[__name__] = _module

__all__ = [
    "DEFAULT_TEMPLATE_PATH",
    "SKILL_GROUP_LABELS",
    "CompilerConfig",
    "CourseworkMode",
    "render_resume",
]
