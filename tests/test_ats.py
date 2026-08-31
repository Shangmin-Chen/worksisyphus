"""Tests for ATS text extraction and formatting."""

from __future__ import annotations

from pathlib import Path

from worksisyphus.ats import check_pdf_ats

ROOT = Path(__file__).resolve().parents[1]


def test_tailored_resume_ats_extraction(deliverable_contact, delivered_pdf) -> None:
    res = check_pdf_ats(
        delivered_pdf,
        name=deliverable_contact.name,
        email=deliverable_contact.email,
        phone=deliverable_contact.phone,
        expected_pages=1,
        require_contact=True,
    )
    assert res.passed, f"ATS check failed: {res.problems}"
    assert res.pages == 1
    assert res.word_count > 300


def test_compiled_resume_ats_extraction(deliverable_contact, canonical_pdf) -> None:
    res = check_pdf_ats(
        canonical_pdf,
        name=deliverable_contact.name,
        email=deliverable_contact.email,
        phone=deliverable_contact.phone,
        expected_pages=3,
        require_contact=True,
    )
    assert res.passed, f"ATS check failed for compiled: {res.problems}"
    assert res.pages == 3
    assert res.word_count > 800


def test_check_pdf_ats_missing_file() -> None:
    res = check_pdf_ats(Path("nonexistent.pdf"))
    assert not res.passed
    assert "File not found" in res.problems[0]


PLACEHOLDER_RESUME_TEXT = (
    "Simon Chen\nsimon@example.com $|$ 555-555-5555\n"
    "Education\nBoston University\nExperience\nSoftware Engineer\nTechnical Skills\n" + "filler word " * 400
)


def _fake_extraction(tmp_path, monkeypatch, text: str, pages: int = 1) -> Path:
    """A PDF whose extracted text is whatever the test says. Keeps the suite off pdflatex."""
    import worksisyphus.ats as ats_module

    pdf = tmp_path / "Simon_Chen_Resume.pdf"
    pdf.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(ats_module, "extract_text", lambda _path: text)
    monkeypatch.setattr(ats_module.PDFPage, "get_pages", lambda _fh: [object()] * pages)
    return pdf


def test_empty_expected_contact_is_skipped_without_require_contact(tmp_path, monkeypatch) -> None:
    """The lenient default, preserved for callers that only want the extracted text."""
    pdf = _fake_extraction(tmp_path, monkeypatch, PLACEHOLDER_RESUME_TEXT)
    res = check_pdf_ats(pdf, name="Simon Chen", email="", phone="", expected_pages=1)
    assert res.passed, res.problems


def test_empty_expected_contact_is_itself_a_problem_when_required(tmp_path, monkeypatch) -> None:
    """Regression: an empty expectation used to silently skip the check.

    That is how a resume addressed to simon@example.com and 555-555-5555 was reported clean:
    nothing was passed to compare against, so nothing was compared. Under require_contact,
    "I cannot verify this" is a problem in its own right.
    """
    pdf = _fake_extraction(tmp_path, monkeypatch, PLACEHOLDER_RESUME_TEXT)
    res = check_pdf_ats(pdf, name="Simon Chen", email="", phone="", expected_pages=1, require_contact=True)
    assert not res.passed
    assert any("contact email not provided" in problem for problem in res.problems)
    assert any("contact phone not provided" in problem for problem in res.problems)
    assert not any("contact name" in problem for problem in res.problems)


def test_require_contact_still_reports_a_mismatch(tmp_path, monkeypatch) -> None:
    pdf = _fake_extraction(tmp_path, monkeypatch, PLACEHOLDER_RESUME_TEXT)
    res = check_pdf_ats(
        pdf,
        name="Simon Chen",
        email="simon@real.dev",
        phone="617-201-4477",
        expected_pages=1,
        require_contact=True,
    )
    assert not res.passed
    assert any("did not extract" in problem for problem in res.problems)
