"""Parser Port: Abstract boundary protocol for PDF text extraction and ATS inspection."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Protocol, runtime_checkable

CANONICAL_STEM = "Simon_Chen_Resume_Compiled"


class ATSCheckResult(NamedTuple):
    """Result of ATS extraction and compliance checks on a PDF resume."""

    passed: bool
    problems: tuple[str, ...]
    pages: int
    word_count: int
    text: str
    warnings: tuple[str, ...] = ()


def scoring_text(result: ATSCheckResult) -> str | None:
    """Return extracted text for evaluator paths, or None when extraction failed."""
    return result.text if result.text.strip() else None


@runtime_checkable
class AtsExtractorPort(Protocol):
    """Port interface for inspecting a PDF with ATS-style parsing."""

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
        """Extract text from PDF and verify presence of candidate contact and sections."""
        ...
