"""Tests for ATS text extraction and formatting."""

from __future__ import annotations

from pathlib import Path

from worksisyphus.ats import check_pdf_ats

ROOT = Path(__file__).resolve().parents[1]


def test_tailored_resume_ats_extraction(real_profile, delivered_pdf) -> None:
    has_real_profile = (ROOT / "profile.json").is_file()
    res = check_pdf_ats(
        delivered_pdf,
        name=real_profile.contact.name,
        email=real_profile.contact.email if has_real_profile else "",
        phone=real_profile.contact.phone if has_real_profile else "",
        expected_pages=1,
    )
    assert res.passed, f"ATS check failed: {res.problems}"
    assert res.pages == 1
    assert res.word_count > 300


def test_compiled_resume_ats_extraction(real_profile, canonical_pdf) -> None:
    has_real_profile = (ROOT / "profile.json").is_file()
    res = check_pdf_ats(
        canonical_pdf,
        name=real_profile.contact.name,
        email=real_profile.contact.email if has_real_profile else "",
        phone=real_profile.contact.phone if has_real_profile else "",
        expected_pages=3,
    )
    assert res.passed, f"ATS check failed for compiled: {res.problems}"
    assert res.pages == 3
    assert res.word_count > 800


def test_check_pdf_ats_missing_file() -> None:
    res = check_pdf_ats(Path("nonexistent.pdf"))
    assert not res.passed
    assert "File not found" in res.problems[0]
