"""Foolproof quality gates for resume compilation, ATS extraction, and policy enforcement."""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from .ats import CANONICAL_STEM, ATSCheckResult, check_pdf_ats

BANNED_TOOLS = (
    "sonarr",
    "radarr",
    "prowlarr",
    "jellyfin",
    "qbittorrent",
    "slskd",
    "soulseek",
)

BANNED_METRIC_PATTERNS = (
    r"uptime by 15%",
    r"100% incident resolution",
)

GPA_PATTERNS = (
    r"\bgpa\b",
    r"grade point average",
    r"\b[234]\.\d{1,2}\s*/\s*4(?:\.0)?\b",
)

LATEX_LEAK_PATTERNS = (
    r"\\textbf\{",
    r"\\resumeItem\{",
    r"\\resumeSubheading",
    r"\\resumeProjectHeading",
    r"\\resumeItemListStart",
    r"\\resumeItemListEnd",
    r"\\vspace\{",
    r"\\emph\{",
)


class GateResult(NamedTuple):
    gate_name: str
    passed: bool
    diagnostics: tuple[str, ...] = ()


def check_gpa_gate(text: str) -> GateResult:
    """Ensure no GPA metrics appear on the resume (Simon's policy)."""
    violations = []
    for pattern in GPA_PATTERNS:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            violations.append(f"Found GPA reference matching {pattern!r}: {matches}")
    return GateResult(
        gate_name="No-GPA Gate",
        passed=len(violations) == 0,
        diagnostics=tuple(violations),
    )


def check_banned_content_gate(text: str) -> GateResult:
    """Ensure no piracy-adjacent tools or fake-sounding metrics appear."""
    violations = []
    lower = text.lower()
    for tool in BANNED_TOOLS:
        if re.search(rf"\b{re.escape(tool)}\b", lower):
            violations.append(f"Found banned tooling name: {tool!r}")
    for pattern in BANNED_METRIC_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            violations.append(f"Found banned metric pattern: {pattern!r}")
    return GateResult(
        gate_name="Banned Content Gate",
        passed=len(violations) == 0,
        diagnostics=tuple(violations),
    )


def check_latex_leak_gate(text: str) -> GateResult:
    """Ensure raw LaTeX control sequences do not leak into the extracted text layer."""
    violations = []
    for pattern in LATEX_LEAK_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            violations.append(f"Found unrendered LaTeX code in PDF text: {matches}")
    return GateResult(
        gate_name="LaTeX Code Leak Gate",
        passed=len(violations) == 0,
        diagnostics=tuple(violations),
    )


def check_density_gate(text: str, is_tailored: bool = True) -> GateResult:
    """Ensure resume contains substantive content density and is not an empty shell."""
    words = len(text.split())
    chars = len(text.strip())
    min_words = 350 if is_tailored else 900
    min_chars = 1500 if is_tailored else 4000

    violations = []
    if words < min_words:
        violations.append(f"Word count too low: {words} words (expected >= {min_words})")
    if chars < min_chars:
        violations.append(f"Character count too low: {chars} chars (expected >= {min_chars})")

    return GateResult(
        gate_name="Content Density Gate",
        passed=len(violations) == 0,
        diagnostics=tuple(violations),
    )


def run_resume_gates(
    pdf_path: Path,
    candidate_name: str = "",
    candidate_email: str = "",
    candidate_phone: str = "",
    expected_pages: int | None = None,
    *,
    require_contact: bool = True,
) -> tuple[tuple[GateResult, ...], ATSCheckResult]:
    """Run every quality gate and return both the results and the ATS extraction they were derived from.

    Callers that need the extraction (word counts, warnings) should use this rather than
    re-running check_pdf_ats, which would parse the PDF a second time.

    ``require_contact`` defaults to True: these gates guard delivery, so an unverifiable
    contact field is a gate failure, not a skipped check. Diagnostic callers that only have
    a name to hand (the evaluator) pass False explicitly.
    """
    ats_res = check_pdf_ats(
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
    is_tailored = (expected_pages == 1) or (pdf_path.stem != CANONICAL_STEM)

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
) -> tuple[GateResult, ...]:
    """Run the complete battery of foolproof quality gates against a compiled resume."""
    gates, _ = run_resume_gates(
        pdf_path,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_phone=candidate_phone,
        expected_pages=expected_pages,
        require_contact=require_contact,
    )
    return gates
