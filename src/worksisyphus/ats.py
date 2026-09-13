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

# renderer.py emits, unconditionally-then-conditionally:
#   if profile.education:      -> "Education"
#   if selection.experiences:  -> "Experience"
#   if selection.projects:     -> "Projects"
#   if selection.skills:       -> "Technical Skills"
# "Education" is always required: it comes straight from profile.json, not a plan selection.
# "Technical Skills" is ALSO hard-required here even though it is technically selection-driven:
# an audit of every published plan (applications/*/plan.json, 52/52) found zero plans with an
# empty `skills` list -- plans: 52 | missing skills: 0 | missing experiences: 0 | missing
# projects: 0. On the real delivery path a resume with no Technical Skills header has never
# happened; treating it as optional would only hide a genuine extraction failure (the header
# silently failing to extract) behind whatever else happened to render. Keep it required so
# that failure mode still trips the gate.
# "Experience" and "Projects" are the genuinely conditional pair: plan.py enforces "at least
# one of experiences/projects" on every plan, so exactly one of the two headers is sometimes
# absent by design (a projects-only plan has no "Experience" header at all) -- ats.py has no
# visibility into the Selection that produced the PDF, so it cannot know which of the two was
# *intended*, only that plan.py guarantees at least one always is. Require at least one rather
# than both, so a valid projects-only (or experience-only) plan is not rejected.
# Do NOT relax this further to "any one of the four" -- that was tried and reverted: it let a
# Technical Skills extraction failure pass silently as long as Experience or Projects still
# extracted, which is a real coverage loss on every one of the 52/52 plans that actually have
# a Technical Skills section, traded for a projects-only case that -- while valid -- has never
# occurred in practice. See git history for the reverted single-bucket version.
ALWAYS_REQUIRED_SECTIONS = ("Education", "Technical Skills")
CONTENT_SECTION_CANDIDATES = ("Experience", "Projects")


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
