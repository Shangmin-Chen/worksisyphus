"""Tests for the resume evaluator and scoring engine."""

from __future__ import annotations

from pathlib import Path

from worksisyphus.evaluator import (
    GATE_COMPLIANCE_MAX,
    IMPACT_METRICS_MAX,
    ROLE_ALIGNMENT_MAX,
    TECHNICAL_DEPTH_MAX,
    evaluate_pdf_against_jd,
    evaluate_resume_text,
    format_evaluation_report,
    selection_to_plain_text,
)
from worksisyphus.plan import parse_plan

ROOT = Path(__file__).resolve().parents[1]


def test_evaluate_resume_text_high_alignment() -> None:
    resume = """
    Simon Chen - Software Engineer
    Languages: C++, Python, Rust, SQL
    Experience: Built low-latency C++ trading pipeline achieving 20µs latency and 100K queries.
    Reduced memory footprint by 45% using lock-free SPSC ring buffers resulting in 2.5x speedup.
    """
    jd = "Looking for a C++ and Python engineer with low-latency and concurrency experience."

    report = evaluate_resume_text(resume, jd)
    assert report.overall_score >= 70
    assert report.gate_compliance_score == 0
    assert report.role_alignment_score >= 30

    assert report.technical_depth_score >= 20
    assert "c++" in report.matched_keywords
    assert "python" in report.matched_keywords
    assert "2.5x" in report.extracted_metrics
    assert len(report.extracted_metrics) >= 3


def test_evaluate_resume_text_missing_keywords() -> None:
    resume = "Python web developer using Django and PostgreSQL."
    jd = "Requires Rust, Kubernetes, and Kafka."

    report = evaluate_resume_text(resume, jd)
    assert "rust" in report.missing_keywords
    assert "kubernetes" in report.missing_keywords
    assert any("Consider highlighting" in s for s in report.suggestions)


def test_evaluate_resume_missing_pdf_gate_failure() -> None:
    missing_pdf = Path("definitely_missing_resume.pdf")
    report = evaluate_resume_text(
        resume_text="Python developer",
        jd_text="Python developer",
        pdf_path=missing_pdf,
    )
    assert report.gate_compliance_score == 0
    assert any("PDF file not found" in diag for diag in report.gate_diagnostics)


def test_selection_to_plain_text(small_profile) -> None:
    plan_json = '{"experiences": ["org-a"], "projects": ["proj1"]}'
    selection = parse_plan(plan_json, small_profile)
    plain_text = selection_to_plain_text(selection, small_profile)

    assert small_profile.contact.name in plain_text
    assert "Engineer" in plain_text
    assert "Proj1" in plain_text
    assert "Python" in plain_text


def test_format_evaluation_report() -> None:
    report = evaluate_resume_text(
        resume_text="C++ developer with 20µs latency optimizations.",
        jd_text="C++ systems developer.",
    )
    formatted = format_evaluation_report(report, target_role="Systems SWE")
    assert "RESUME EVALUATION REPORT: SYSTEMS SWE" in formatted
    assert "Overall Match Score" in formatted
    assert "SCORE BREAKDOWN:" in formatted


def test_evaluate_pdf_against_jd(delivered_pdf) -> None:
    jd = "Software Engineer with experience in C++, Python, distributed systems, and performance tuning."
    report = evaluate_pdf_against_jd(delivered_pdf, jd)
    assert report.overall_score >= 70
    assert report.gate_compliance_score == 10


def test_scoring_constants_match_the_reported_maxima() -> None:
    """A mechanical gate: a future constant edit that desyncs the report header must fail the build."""
    assert ROLE_ALIGNMENT_MAX + TECHNICAL_DEPTH_MAX + IMPACT_METRICS_MAX + GATE_COMPLIANCE_MAX == 100

    report = evaluate_resume_text(
        resume_text="C++ developer with 20µs latency optimizations.",
        jd_text="C++ systems developer.",
    )
    formatted = format_evaluation_report(report)
    assert f"/ {ROLE_ALIGNMENT_MAX}" in formatted
    assert f"/ {TECHNICAL_DEPTH_MAX}" in formatted
    assert f"/ {IMPACT_METRICS_MAX}" in formatted
    assert f"/ {GATE_COMPLIANCE_MAX}" in formatted


def test_evaluator_scores_are_unchanged_by_the_constant_extraction() -> None:
    """Characterization test: hoisting magic numbers to named constants must change no value.

    These are the exact component scores produced before the constants were named (recorded by
    running this same resume/JD -- the ones used by test_evaluate_resume_text_high_alignment --
    prior to the extraction). If a future edit to the constants changes these numbers, that is a
    real behavior change and this test should be updated deliberately, not silently.
    """
    resume = """
    Simon Chen - Software Engineer
    Languages: C++, Python, Rust, SQL
    Experience: Built low-latency C++ trading pipeline achieving 20µs latency and 100K queries.
    Reduced memory footprint by 45% using lock-free SPSC ring buffers resulting in 2.5x speedup.
    """
    jd = "Looking for a C++ and Python engineer with low-latency and concurrency experience."

    report = evaluate_resume_text(resume, jd)

    assert report.role_alignment_score == 33
    assert report.technical_depth_score == 30
    assert report.impact_metrics_score == 12
    assert report.gate_compliance_score == 0
    assert report.overall_score == 75


def test_evaluate_resume_text_skipped_gates_scores_zero() -> None:
    """When gate_results is None and pdf_path is None, gates did not run and must score 0."""
    report = evaluate_resume_text("Python engineer", "Python engineer")
    assert report.gate_compliance_score == 0
    assert any("not evaluated" in diag for diag in report.gate_diagnostics)


def test_evaluate_resume_text_with_explicit_passing_gates_scores_ten() -> None:
    from worksisyphus.gates import GateResult

    report = evaluate_resume_text(
        "Python engineer",
        "Python engineer",
        gate_results=(GateResult("Dummy Gate", True),),
    )
    assert report.gate_compliance_score == 10
