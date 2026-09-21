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
    assert not check_gpa_gate("G.P.A. 3.8").passed
    assert not check_gpa_gate("G. P. A.: 3.9").passed
    assert not check_gpa_gate("g.p.a 3.7").passed
    assert not check_gpa_gate("Grade-Point Average: 3.85").passed
    assert not check_gpa_gate("Grade Point-Average: 3.85").passed
    assert not check_gpa_gate("G,P,A 3.8").passed
    assert not check_gpa_gate("G/P/A 3.8").passed
    assert not check_gpa_gate("G_P_A 3.8").passed
    assert not check_gpa_gate("G P A 3.8").passed
    assert not check_gpa_gate("G . P . A 3.8").passed
    assert not check_gpa_gate("G-P-A 3.8").passed
    assert not check_gpa_gate("CGPA 3.9").passed
    assert not check_gpa_gate("CGPA: 3.85").passed
    assert not check_gpa_gate("C.G.P.A. 3.75").passed
    assert not check_gpa_gate("GPA3.8").passed
    assert not check_gpa_gate("CGPA3.85").passed
    assert not check_gpa_gate("G P A3.8").passed
    assert not check_gpa_gate("C.G.P.A3.85").passed
    assert not check_gpa_gate("CGPA: 3.8").passed
    assert not check_gpa_gate("GPA3.9").passed
    assert check_gpa_gate("Python 3.11 / 4 worker processes").passed
    assert check_gpa_gate("Python 3.10 / 4 threads").passed
    assert check_gpa_gate("Engineered high-throughput service on Python 3.11 / 4 worker processes").passed
    assert not check_gpa_gate("GPA4").passed
    assert not check_gpa_gate("GPA3").passed
    assert not check_gpa_gate("CGPA4").passed
    assert not check_gpa_gate("CGPA3").passed
    assert not check_gpa_gate("GPA3.856").passed
    assert not check_gpa_gate("G PA 3.8").passed
    assert not check_gpa_gate("G PA3.8").passed
    assert not check_gpa_gate("GPA_3.8").passed
    assert not check_gpa_gate("CGPA_3.85").passed
    assert not check_gpa_gate("GPA4.0").passed
    assert not check_gpa_gate("CGPA3.8").passed
    assert not check_gpa_gate("CGPA4.0").passed
    assert not check_gpa_gate("GPA2.8").passed
    assert not check_gpa_gate("GPA2.5").passed
    assert not check_gpa_gate("GPA1.9").passed
    assert not check_gpa_gate("CGPA2.8").passed
    assert not check_gpa_gate("GPA_2.0").passed
    assert not check_gpa_gate("CGPA_2.0").passed
    assert not check_gpa_gate("GPA2.0/4.0").passed
    assert not check_gpa_gate("GPA2.0-beta").passed
    assert not check_gpa_gate("GPA2.0x").passed
    assert not check_gpa_gate("GPA2.0API").passed
    assert not check_gpa_gate("GPA2.0").passed
    assert not check_gpa_gate("CGPA2.0").passed
    assert not check_gpa_gate("GPA2.0.").passed
    assert not check_gpa_gate("GPA2.0,").passed
    assert not check_gpa_gate("CGPA2.0.").passed
    assert not check_gpa_gate("GPA2.0, on a 4.0 scale").passed
    assert not check_gpa_gate("GPA2.0 out of 4.0").passed
    assert not check_gpa_gate("CGPA2.0 out of 4.0").passed
    assert not check_gpa_gate("GPA2.0.beta").passed
    assert not check_gpa_gate("GPA2.0,4.0").passed


def test_gpa_gate_does_not_fire_on_bare_decimals_or_metrics() -> None:
    """Gating bare decimals would flag real metrics like '3.85x speedup'."""
    assert check_gpa_gate("Achieved 3.85x speedup on the hot path").passed
    assert check_gpa_gate("Reduced p99 latency to 3.8ms").passed
    assert check_gpa_gate("Shipped 4.0 of the platform").passed
    assert check_gpa_gate("Debug log p a value before shipping").passed
    assert check_gpa_gate("Going past a checkpoint on the hot path").passed
    assert check_gpa_gate("Completed GPA2 certification module").passed
    assert check_gpa_gate("GPA2 platform deployment").passed
    assert not check_gpa_gate("Deployed GPA2.0 platform").passed
    assert not check_gpa_gate("Completed GPA2.0 certification module").passed
    assert not check_gpa_gate("GPA2.0 API compatibility module").passed
    assert not check_gpa_gate("Completed CGPA2.0 certification module").passed
    assert not check_gpa_gate("Graduated with GPA2.0 platform honors").passed
    assert not check_gpa_gate("GPA2.0 API score 2.0").passed
    assert check_gpa_gate("Deployed on GPA360 hardware platform").passed
    assert check_gpa_gate("G PA360 hardware platform").passed
    assert check_gpa_gate("GPA2024 annual review cycle").passed
    assert check_gpa_gate("CGPA360 integration test suite").passed


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


def test_density_gate_is_strict_for_a_multi_page_expectation(tmp_path, monkeypatch) -> None:
    """expected_pages must win over the filename heuristic for is_tailored.

    A non-canonical filename used to force is_tailored=True regardless of expected_pages,
    applying the lenient 350-word tailored floor to a document explicitly expected to be
    the 3-page canonical (900-word floor). This proved the bug and now proves the fix.
    """
    import worksisyphus.gates as gates_module
    from worksisyphus.ats import ATSCheckResult
    from worksisyphus.gates import run_resume_gates

    def fake_ats(pdf_path, **kwargs) -> ATSCheckResult:
        return ATSCheckResult(
            passed=True,
            problems=(),
            pages=kwargs.get("expected_pages") or 1,
            word_count=500,
            text="word " * 500,
            warnings=(),
        )

    monkeypatch.setattr(gates_module, "check_pdf_ats", fake_ats)

    pdf = tmp_path / "Some_Other_Name.pdf"

    multi_page_gates, _ = run_resume_gates(pdf, candidate_name="Simon Chen", expected_pages=3)
    density_gate = next(g for g in multi_page_gates if g.gate_name == "Content Density Gate")
    assert not density_gate.passed

    one_page_gates, _ = run_resume_gates(pdf, candidate_name="Simon Chen", expected_pages=1)
    density_gate_one = next(g for g in one_page_gates if g.gate_name == "Content Density Gate")
    assert density_gate_one.passed


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


def test_profile_gates_scan_profile_for_gpa_and_banned_content(small_profile) -> None:
    import dataclasses

    from worksisyphus.gates import check_profile_gates
    from worksisyphus.profile import Experience

    # Clean profile passes
    assert all(g.passed for g in check_profile_gates(small_profile))

    # GPA in profile bullet fails
    bad_gpa_exp = Experience(
        id="org-a",
        role="SWE",
        org="Org",
        location="NY",
        date="2025",
        bullets={"a1": "Graduated with 3.9 GPA"},
    )
    bad_gpa_profile = dataclasses.replace(
        small_profile,
        experiences={"org-a": bad_gpa_exp},
    )
    gpa_results = check_profile_gates(bad_gpa_profile)
    assert any(not g.passed and g.gate_name == "No-GPA Gate" for g in gpa_results)

    # Banned content in profile bullet fails
    bad_tool_exp = Experience(
        id="org-a",
        role="SWE",
        org="Org",
        location="NY",
        date="2025",
        bullets={"a1": "Configured Jellyfin and Sonarr stack"},
    )
    bad_tool_profile = dataclasses.replace(
        small_profile,
        experiences={"org-a": bad_tool_exp},
    )
    banned_results = check_profile_gates(bad_tool_profile)
    assert any(not g.passed and g.gate_name == "Banned Content Gate" for g in banned_results)


def test_pipeline_refuses_to_build_when_profile_fails_gates(small_profile, tmp_path) -> None:
    import dataclasses

    import pytest

    from worksisyphus import pipeline
    from worksisyphus.profile import Experience

    bad_exp = Experience(
        id="org-a",
        role="SWE",
        org="Org",
        location="NY",
        date="2025",
        bullets={"a1": "Maintained 3.9 GPA in CS"},
    )
    bad_profile = dataclasses.replace(small_profile, experiences={"org-a": bad_exp})

    # tailor must refuse
    with pytest.raises(RuntimeError, match="Profile policy gate failed"):
        pipeline.tailor('{"experiences": ["org-a"]}', profile=bad_profile, tex_dir=tmp_path, pdf_dir=tmp_path)


