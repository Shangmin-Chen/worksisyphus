"""Backward-compatibility facade for pipeline tailoring and canonical build."""

from __future__ import annotations

import sys

from .core.use_cases import pipeline as _module
from .core.use_cases.pipeline import (
    OVERFULL_TOLERANCE_PT,
    PAGE_LIMIT,
    PREVIEW_DIR,
    TEX_DIR,
    Log,
    build_canonical,
    compile_tex,
    load_profile,
    tailor,
)

sys.modules[__name__] = _module

__all__ = [
    "OVERFULL_TOLERANCE_PT",
    "PAGE_LIMIT",
    "PREVIEW_DIR",
    "TEX_DIR",
    "Log",
    "build_canonical",
    "compile_tex",
    "load_profile",
    "tailor",
]
