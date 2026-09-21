"""Backward-compatibility facade for ATS text extraction and check."""

from __future__ import annotations

import sys

from pdfminer.pdfpage import PDFPage

from .adapters.outbound.pdf import ats_parser as _module
from .adapters.outbound.pdf.ats_parser import (
    CANONICAL_STEM,
    MERGED_DATE_RE,
    PdfMinerAtsAdapter,
    check_pdf_ats,
)
from .ports.parser import ATSCheckResult, AtsExtractorPort, scoring_text

sys.modules[__name__] = _module

__all__ = [
    "CANONICAL_STEM",
    "MERGED_DATE_RE",
    "ATSCheckResult",
    "AtsExtractorPort",
    "PDFPage",
    "PdfMinerAtsAdapter",
    "check_pdf_ats",
    "scoring_text",
]
