"""Resume quality gate coordination use case."""

from __future__ import annotations

from pathlib import Path

from ...adapters.outbound.pdf.ats_parser import check_pdf_ats as _default_check_pdf_ats
from ...ports.parser import CANONICAL_STEM, ATSCheckResult, AtsExtractorPort
from ..domain.gates import (
    BANNED_METRIC_PATTERNS,
    BANNED_TOOLS,
    GPA_PATTERNS,
    LATEX_LEAK_PATTERNS,
    MIN_WORDS_COMPILED,
    MIN_WORDS_TAILORED,
    GateResult,
    check_banned_content_gate,
    check_density_gate,
    check_gpa_gate,
    check_latex_leak_gate,
    check_profile_gates,
)

check_pdf_ats = _default_check_pdf_ats


class _DefaultAtsExtractor(AtsExtractorPort):
    def check_pdf_ats(
        self,
        pdf_path: Path,
        name: str = "",
        email: str = "",
        phone: str = "",
        expected_pages: int | None = None,
        *,
        require_contact: bool = False,
    ) -> ATSCheckResult:
        return check_pdf_ats(
            pdf_path=pdf_path,
            name=name,
            email=email,
            phone=phone,
            expected_pages=expected_pages,
            require_contact=require_contact,
        )


def _get_default_ats_extractor() -> AtsExtractorPort:
    return _DefaultAtsExtractor()


def run_resume_gates(
    pdf_path: Path,
    candidate_name: str = "",
    candidate_email: str = "",
    candidate_phone: str = "",
    expected_pages: int | None = None,
    *,
    require_contact: bool = True,
    extractor: AtsExtractorPort | None = None,
) -> tuple[tuple[GateResult, ...], ATSCheckResult]:
    """Run every quality gate and return both results and ATS extraction."""
    active_extractor = extractor or _get_default_ats_extractor()
    ats_res = active_extractor.check_pdf_ats(
        pdf_path=pdf_path,
        name=candidate_name,
        email=candidate_email,
        phone=candidate_phone,
        expected_pages=expected_pages,
        require_contact=require_contact,
    )

    ats_gate = GateResult(
        gate_name="ATS Extraction & Page Count Gate",
        passed=ats_res.passed,
        diagnostics=ats_res.problems,
    )

    text = ats_res.text

    if expected_pages is not None:
        is_tailored = expected_pages == 1
    else:
        is_tailored = pdf_path.stem != CANONICAL_STEM

    gates = (
        ats_gate,
        check_gpa_gate(text),
        check_banned_content_gate(text),
        check_latex_leak_gate(text),
        check_density_gate(text, is_tailored=is_tailored),
    )
    return gates, ats_res


def check_resume_gates(
    pdf_path: Path,
    candidate_name: str = "",
    candidate_email: str = "",
    candidate_phone: str = "",
    expected_pages: int | None = None,
    *,
    require_contact: bool = True,
    extractor: AtsExtractorPort | None = None,
) -> tuple[GateResult, ...]:
    """Run the complete battery of foolproof quality gates against a compiled resume."""
    gates, _ = run_resume_gates(
        pdf_path,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_phone=candidate_phone,
        expected_pages=expected_pages,
        require_contact=require_contact,
        extractor=extractor,
    )
    return gates


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

