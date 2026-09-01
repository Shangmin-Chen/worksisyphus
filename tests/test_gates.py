"""Automated tests for foolproof resume quality gates."""

from __future__ import annotations

from pathlib import Path

from worksisyphus.gates import (
    check_banned_content_gate,
    check_density_gate,
    check_gpa_gate,
    check_latex_leak_gate,
    check_resume_gates,
)
from worksisyphus.selection import TAILORED_NAME

ROOT = Path(__file__).resolve().parents[1]


def test_tailored_resume_passes_all_gates(deliverable_contact, delivered_pdf) -> None:
    """Every delivered resume lives in applications/; gate the most recent one."""

    gates = check_resume_gates(
        pdf_path=delivered_pdf,
        candidate_name=deliverable_contact.name,
        candidate_email=deliverable_contact.email,
        candidate_phone=deliverable_contact.phone,
        expected_pages=1,
    )

    failed_gates = [g for g in gates if not g.passed]
    assert not failed_gates, f"Gates failed: {[(g.gate_name, g.diagnostics) for g in failed_gates]}"


def test_compiled_resume_passes_all_gates(deliverable_contact, canonical_pdf) -> None:
    gates = check_resume_gates(
        pdf_path=canonical_pdf,
        candidate_name=deliverable_contact.name,
        candidate_email=deliverable_contact.email,
        candidate_phone=deliverable_contact.phone,
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


def test_gates_fail_closed_when_contact_cannot_be_verified(tmp_path, monkeypatch) -> None:
    """The proven bug: run_resume_gates(candidate_email="") once returned ALL GATES PASS.

    The PDF's header says simon@example.com. Nothing was passed to contradict it, so every
    gate agreed the resume was deliverable. run_resume_gates is the delivery path, so it now
    requires the contact by default; a diagnostic caller opts out explicitly.
    """
    import worksisyphus.ats as ats_module
    from worksisyphus.gates import run_resume_gates

    pdf = tmp_path / "Simon_Chen_Resume.pdf"
    pdf.write_bytes(b"%PDF-fake")
    text = (
        "Simon Chen\nsimon@example.com $|$ 555-555-5555\n"
        "Education\nBoston University\nExperience\nEngineer\nTechnical Skills\n" + "filler word " * 400
    )
    monkeypatch.setattr(ats_module, "extract_text", lambda _path: text)
    monkeypatch.setattr(ats_module.PDFPage, "get_pages", lambda _fh: [object()])

    strict, _ = run_resume_gates(pdf, candidate_name="Simon Chen", candidate_email="", expected_pages=1)
    ats_gate = next(g for g in strict if g.gate_name.startswith("ATS"))
    assert not ats_gate.passed
    assert any("not provided" in d for d in ats_gate.diagnostics)

    lenient, _ = run_resume_gates(
        pdf, candidate_name="Simon Chen", candidate_email="", expected_pages=1, require_contact=False
    )
    assert all(g.passed for g in lenient), [(g.gate_name, g.diagnostics) for g in lenient]
