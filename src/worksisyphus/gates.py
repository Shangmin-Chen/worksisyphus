"""Backward-compatibility facade for quality gates."""

from __future__ import annotations

import sys

from .core.use_cases import gates as _module
from .core.use_cases.gates import (
    BANNED_METRIC_PATTERNS,
    BANNED_TOOLS,
    CANONICAL_STEM,
    GPA_PATTERNS,
    LATEX_LEAK_PATTERNS,
    MIN_WORDS_COMPILED,
    MIN_WORDS_TAILORED,
    ATSCheckResult,
    AtsExtractorPort,
    GateResult,
    check_banned_content_gate,
    check_density_gate,
    check_gpa_gate,
    check_latex_leak_gate,
    check_pdf_ats,
    check_profile_gates,
    check_resume_gates,
    run_resume_gates,
)

sys.modules[__name__] = _module

__all__ = [
    "BANNED_METRIC_PATTERNS",
    "BANNED_TOOLS",
    "CANONICAL_STEM",
    "GPA_PATTERNS",
    "LATEX_LEAK_PATTERNS",
    "MIN_WORDS_COMPILED",
    "MIN_WORDS_TAILORED",
    "ATSCheckResult",
    "AtsExtractorPort",
    "GateResult",
    "check_banned_content_gate",
    "check_density_gate",
    "check_gpa_gate",
    "check_latex_leak_gate",
    "check_pdf_ats",
    "check_profile_gates",
    "check_resume_gates",

    "run_resume_gates",
]
