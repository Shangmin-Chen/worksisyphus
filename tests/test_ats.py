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


def test_check_pdf_ats_reports_a_malformed_pdf_instead_of_raising(tmp_path) -> None:
    """A truncated/non-PDF file must fail closed, not raise a pdfminer exception."""
    pdf = tmp_path / "Simon_Chen_Resume.pdf"
    pdf.write_bytes(b"not a pdf at all")

    res = check_pdf_ats(pdf, expected_pages=1)

    assert res.passed is False
    assert res.pages == 0
    assert res.word_count == 0
    assert res.text == ""
    assert any("could not parse PDF" in problem for problem in res.problems)


def test_check_pdf_ats_reports_an_extraction_exception(tmp_path, monkeypatch) -> None:
    """Deterministic version of the malformed-PDF case: force a specific exception type."""
    import worksisyphus.ats as ats_module

    pdf = tmp_path / "Simon_Chen_Resume.pdf"
    pdf.write_bytes(b"%PDF-fake")

    def _boom(_path):
        raise RuntimeError("boom")

    monkeypatch.setattr(ats_module, "extract_text", _boom)

    res = check_pdf_ats(pdf, expected_pages=1)

    assert res.passed is False
    assert res.pages == 0
    assert res.word_count == 0
    assert res.text == ""
    assert len(res.problems) == 1
    assert "RuntimeError" in res.problems[0]
    assert "boom" in res.problems[0]


def test_malformed_pdf_fails_the_gates_rather_than_crashing_apply(tmp_path) -> None:
    """The delivery path (run_resume_gates) must also fail closed, never raise."""
    from worksisyphus.gates import run_resume_gates

    pdf = tmp_path / "Simon_Chen_Resume.pdf"
    pdf.write_bytes(b"not a pdf at all")

    gates, ats_res = run_resume_gates(pdf, candidate_name="Simon Chen", expected_pages=1)

    assert ats_res.passed is False
    ats_gate = next(g for g in gates if g.gate_name.startswith("ATS"))
    density_gate = next(g for g in gates if g.gate_name == "Content Density Gate")
    assert ats_gate.passed is False
    assert density_gate.passed is False


def test_projects_only_resume_passes_without_an_experience_section(tmp_path, monkeypatch) -> None:
    """A valid projects-only plan renders with no Experience section and must not be rejected."""
    text = (
        "Simon Chen\nsimon@example.com $|$ 555-555-5555\n"
        "Education\nBoston University\n"
        "Projects\nPersephone C++ trading engine\n"
        "Technical Skills\nC++, Python\n" + "filler word " * 400
    )
    pdf = _fake_extraction(tmp_path, monkeypatch, text)

    res = check_pdf_ats(pdf, name="Simon Chen", email="", phone="", expected_pages=1)

    assert res.passed, res.problems
    assert not any("Experience" in problem for problem in res.problems)
