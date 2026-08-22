"""Automated tests for foolproof resume quality gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from worksisyphus.gates import (
    check_banned_content_gate,
    check_density_gate,
    check_gpa_gate,
    check_latex_leak_gate,
    check_resume_gates,
)
from worksisyphus.selection import TAILORED_NAME

ROOT = Path(__file__).resolve().parents[1]
TAILORED_PDF = ROOT / "resumes" / "Simon_Chen_Resume.pdf"
COMPILED_PDF = ROOT / "resumes" / "Simon_Chen_Resume_Compiled.pdf"


def test_tailored_resume_passes_all_gates(real_profile) -> None:
    if not TAILORED_PDF.is_file():
        pytest.skip(f"{TAILORED_PDF} not present")

    has_real_profile = (ROOT / "profile.json").is_file()
    gates = check_resume_gates(
        pdf_path=TAILORED_PDF,
        candidate_name=real_profile.contact.name,
        candidate_email=real_profile.contact.email if has_real_profile else "",
        candidate_phone=real_profile.contact.phone if has_real_profile else "",
        expected_pages=1,
    )

    failed_gates = [g for g in gates if not g.passed]
    assert not failed_gates, f"Gates failed: {[(g.gate_name, g.diagnostics) for g in failed_gates]}"


def test_compiled_resume_passes_all_gates(real_profile) -> None:
    if not COMPILED_PDF.is_file():
        pytest.skip(f"{COMPILED_PDF} not present")

    has_real_profile = (ROOT / "profile.json").is_file()
    gates = check_resume_gates(
        pdf_path=COMPILED_PDF,
        candidate_name=real_profile.contact.name,
        candidate_email=real_profile.contact.email if has_real_profile else "",
        candidate_phone=real_profile.contact.phone if has_real_profile else "",
        expected_pages=3,
    )

    failed_gates = [g for g in gates if not g.passed]
    assert not failed_gates, f"Gates failed: {[(g.gate_name, g.diagnostics) for g in failed_gates]}"


def test_gpa_gate_catches_violations() -> None:
    assert check_gpa_gate("Clean text without any grade info").passed
    assert not check_gpa_gate("Graduated with 3.85 / 4.0 GPA").passed
    assert not check_gpa_gate("GPA: 3.9").passed
    assert not check_gpa_gate("Cumulative grade point average: 3.7").passed


def test_banned_content_gate_catches_piracy_and_fake_metrics() -> None:
    assert check_banned_content_gate("Built distributed streaming pipeline in Rust").passed
    assert not check_banned_content_gate("Managed media library using Sonarr and Radarr").passed
    assert not check_banned_content_gate("Configured Jellyfin and qBittorrent stack").passed
    assert not check_banned_content_gate("Achieved 100% incident resolution in 24h").passed
    assert not check_banned_content_gate("Boosted system uptime by 15% across clusters").passed


def test_latex_leak_gate_catches_unrendered_macros() -> None:
    assert check_latex_leak_gate("Normal extracted text with bullet points").passed
    assert not check_latex_leak_gate(r"Text with unrendered \textbf{bold text}").passed
    assert not check_latex_leak_gate(r"\resumeItem{Implemented Cython kernel}").passed


def test_density_gate_catches_truncated_text() -> None:
    assert not check_density_gate("Too short", is_tailored=True).passed
    long_tailored = "word " * 400
    assert check_density_gate(long_tailored, is_tailored=True).passed


def test_employer_resume_filename_convention() -> None:
    assert TAILORED_NAME == "Simon_Chen_Resume"
    assert not TAILORED_NAME.endswith(".pdf")
    assert "tailored" not in TAILORED_NAME.lower()
    assert "version" not in TAILORED_NAME.lower()


def test_run_resume_gates_extracts_the_pdf_only_once(tmp_path, monkeypatch) -> None:
    """apply() reuses this extraction; re-running check_pdf_ats would parse the PDF twice."""
    import worksisyphus.gates as gates_module
    from worksisyphus.ats import ATSCheckResult
    from worksisyphus.gates import run_resume_gates

    calls = []

    def counting_ats(pdf_path, **kwargs) -> ATSCheckResult:
        calls.append(pdf_path)
        return ATSCheckResult(
            passed=True,
            problems=(),
            pages=1,
            word_count=500,
            text="Simon Chen EXPERIENCE PROJECTS " + ("word " * 500),
            warnings=("merged date",),
        )

    monkeypatch.setattr(gates_module, "check_pdf_ats", counting_ats)

    pdf = tmp_path / "Simon_Chen_Resume.pdf"
    gates, ats_res = run_resume_gates(pdf, candidate_name="Simon Chen", expected_pages=1)

    assert len(calls) == 1
    assert all(g.passed for g in gates)
    # The extraction is handed back so callers get the warnings without re-parsing.
    assert ats_res.warnings == ("merged date",)
    assert ats_res.word_count == 500
