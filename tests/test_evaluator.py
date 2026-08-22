"""Tests for the resume evaluator and scoring engine."""

from __future__ import annotations

from pathlib import Path

from worksisyphus.evaluator import (
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
    assert report.overall_score >= 80
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
