"""PDF ATS Extractor Adapter: Implements AtsExtractorPort using pdfminer.six."""

from __future__ import annotations

import re
from pathlib import Path

from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage

from ....ports.parser import ATSCheckResult

CANONICAL_STEM = "Simon_Chen_Resume_Compiled"
MERGED_DATE_RE = re.compile(
    r"[A-Za-z]{3,}(?:January|February|March|April|May|June|July|August|September|October|November|December) 20\d\d"
)

ALWAYS_REQUIRED_SECTIONS = ("Education", "Technical Skills")
CONTENT_SECTION_CANDIDATES = ("Experience", "Projects")


def scoring_text(result: ATSCheckResult) -> str | None:
    """Return extracted text for evaluator paths, or None when extraction failed."""
    return result.text if result.text.strip() else None


def check_pdf_ats(
    pdf_path: Path,
    name: str = "",
    email: str = "",
    phone: str = "",
    expected_pages: int | None = None,
    *,
    require_contact: bool = False,
) -> ATSCheckResult:
    """Extract text from a PDF and check that standard fields and sections are present."""
    if not pdf_path.is_file():
        return ATSCheckResult(
            passed=False,
            problems=(f"File not found: {pdf_path}",),
            pages=0,
            word_count=0,
            text="",
            warnings=(),
        )

    try:
        text = extract_text(pdf_path)
        with pdf_path.open("rb") as fh:
            pages = sum(1 for _ in PDFPage.get_pages(fh))
    except Exception as exc:
        return ATSCheckResult(
            passed=False,
            problems=(f"could not parse PDF {pdf_path}: {type(exc).__name__}: {exc}",),
            pages=0,
            word_count=0,
            text="",
            warnings=(),
        )

    problems: list[str] = []
    is_canonical = pdf_path.stem == CANONICAL_STEM

    if expected_pages is not None:
        if pages != expected_pages:
            problems.append(f"expected {expected_pages} page(s), got {pages}")
    elif not is_canonical and pages != 1:
        problems.append(f"expected 1 page, got {pages}")

    for label, needle in (("name", name), ("email", email), ("phone", phone)):
        if not needle:
            if require_contact:
                problems.append(f"contact {label} not provided; cannot verify it reached the PDF")
            continue
        if needle not in text:
            problems.append(f"contact {label} {needle!r} did not extract")

    for section in ALWAYS_REQUIRED_SECTIONS:
        if section not in text:
            problems.append(f"section header {section!r} did not extract")

    if not any(section in text for section in CONTENT_SECTION_CANDIDATES):
        problems.append(f"no content section header extracted; expected at least one of {CONTENT_SECTION_CANDIDATES!r}")

    if "(cid:" in text:
        problems.append("broken glyphs: extraction produced (cid:N) placeholders")

    warnings: list[str] = [
        f"{m!r} extracted with no whitespace before the date; that keyword will not match"
        for m in MERGED_DATE_RE.findall(text)
    ]

    words = len(text.split())
    return ATSCheckResult(
        passed=len(problems) == 0,
        problems=tuple(problems),
        pages=pages,
        word_count=words,
        text=text,
        warnings=tuple(warnings),
    )


class PdfMinerAtsAdapter:
    """AtsExtractorPort implementation using pdfminer.six library."""

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
