"""ATS extraction check: verify a compiled resume PDF parses the way a recruiting system would."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage

CANONICAL_STEM = "Simon_Chen_Resume_Compiled"


class ATSCheckResult(NamedTuple):
    passed: bool
    problems: tuple[str, ...]
    pages: int
    word_count: int
    text: str


def check_pdf_ats(
    pdf_path: Path,
    name: str = "",
    email: str = "",
    phone: str = "",
    expected_pages: int | None = None,
) -> ATSCheckResult:
    """Extract text from a PDF and check that standard fields and sections are present."""
    if not pdf_path.is_file():
        return ATSCheckResult(
            passed=False,
            problems=(f"File not found: {pdf_path}",),
            pages=0,
            word_count=0,
            text="",
        )

    text = extract_text(pdf_path)
    with pdf_path.open("rb") as fh:
        pages = sum(1 for _ in PDFPage.get_pages(fh))

    problems: list[str] = []
    is_canonical = pdf_path.stem == CANONICAL_STEM

    if expected_pages is not None:
        if pages != expected_pages:
            problems.append(f"expected {expected_pages} page(s), got {pages}")
    elif not is_canonical and pages != 1:
        problems.append(f"expected 1 page, got {pages}")

    for label, needle in (("name", name), ("email", email), ("phone", phone)):
        if needle and needle not in text:
            problems.append(f"contact {label} {needle!r} did not extract")

    for section in ("Education", "Experience", "Technical Skills"):
        if section not in text:
            problems.append(f"section header {section!r} did not extract")

    if "(cid:" in text:
        problems.append("broken glyphs: extraction produced (cid:N) placeholders")

    words = len(text.split())
    return ATSCheckResult(
        passed=len(problems) == 0,
        problems=tuple(problems),
        pages=pages,
        word_count=words,
        text=text,
    )
