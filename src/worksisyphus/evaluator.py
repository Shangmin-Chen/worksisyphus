"""Backward-compatibility facade for resume and profile evaluation."""

from __future__ import annotations

import sys

from .core.use_cases import evaluator as _module
from .core.use_cases.evaluator import (
    COMMON_TECH_TERMS,
    GATE_COMPLIANCE_MAX,
    IMPACT_METRICS_MAX,
    METRIC_PATTERNS,
    ROLE_ALIGNMENT_MAX,
    TECHNICAL_DEPTH_MAX,
    EvaluationReport,
    evaluate_pdf_against_jd,
    evaluate_resume_text,
    format_evaluation_report,
    selection_to_plain_text,
)

sys.modules[__name__] = _module

__all__ = [
    "COMMON_TECH_TERMS",
    "GATE_COMPLIANCE_MAX",
    "IMPACT_METRICS_MAX",
    "METRIC_PATTERNS",
    "ROLE_ALIGNMENT_MAX",
    "TECHNICAL_DEPTH_MAX",
    "EvaluationReport",
    "evaluate_pdf_against_jd",
    "evaluate_resume_text",
    "format_evaluation_report",
    "selection_to_plain_text",
]
