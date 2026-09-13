"""ATS extraction check: verify a compiled resume PDF parses the way a recruiting system would."""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage

CANONICAL_STEM = "Simon_Chen_Resume_Compiled"
MERGED_DATE_RE = re.compile(
    r"[A-Za-z]{3,}(?:January|February|March|April|May|June|July|August|September|October|November|December) 20\d\d"
)

# renderer.py emits "Education" unconditionally (it comes straight from profile.json, not a
# plan selection), so it is always required. "Experience", "Projects", and "Technical Skills"
# are each emitted only `if selection.<field>` is non-empty (see renderer.py's conditional
# section builders), so a valid plan can legitimately omit any one of them -- e.g. a
# projects-only plan renders with no "Experience" header at all. ats.py has no visibility into
# the Selection that produced the PDF, so it cannot know which of these three were *intended*;
# the best it can require is that at least one of them actually rendered, which still catches
# a genuinely empty/broken body (only "Education" extracted) without rejecting a valid resume
# that simply didn't select one particular content section.
ALWAYS_REQUIRED_SECTIONS = ("Education",)
CONTENT_SECTION_CANDIDATES = ("Experience", "Projects", "Technical Skills")


class ATSCheckResult(NamedTuple):
    passed: bool
    problems: tuple[str, ...]
    pages: int
    word_count: int
    text: str
    warnings: tuple[str, ...] = ()


def check_pdf_ats(
    pdf_path: Path,
    name: str = "",
    email: str = "",
    phone: str = "",
    expected_pages: int | None = None,
    *,
    require_contact: bool = False,
) -> ATSCheckResult:
    """Extract text from a PDF and check that standard fields and sections are present.

    ``require_contact`` decides what an *empty* expected value means. Off (the default) it
    means "not checking that field", which is what the text-extraction callers want: they
    pass only ``name=`` and use the extraction, not the verdict. On, it means "this resume
    is about to be delivered and I cannot verify its contact details", which is a problem in
    its own right -- an empty expectation used to be silently skipped, so passing
    ``candidate_email=""`` for a PDF whose header said simon@example.com reported ALL GATES
    PASS. The delivery path (run_resume_gates) turns it on.
    """
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
        # pdfminer raises a wide, unstable family of exceptions on truncated or non-PDF input
        # (PDFSyntaxError, PSEOF, struct.error, AssertionError, ...). Catching broadly here is
        # deliberate: it converts an unparseable file into an explicit FAILURE, never a pass, so
        # this stays fail-closed all the way through run_resume_gates (empty text also fails the
        # Content Density Gate) instead of raising out of apply's staging block.
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
        problems.append(
            "no content section header extracted; expected at least one of "
            f"{CONTENT_SECTION_CANDIDATES!r}"
        )

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
