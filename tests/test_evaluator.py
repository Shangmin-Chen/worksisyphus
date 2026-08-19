"""Tests for the resume evaluator and scoring engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from worksisyphus.evaluator import (
    evaluate_pdf_against_jd,
    evaluate_resume_text,
    format_evaluation_report,
)

ROOT = Path(__file__).resolve().parents[1]
TAILORED_PDF = ROOT / "resumes" / "Simon_Chen_Resume.pdf"


def test_evaluate_resume_text_high_alignment() -> None:
    resume = """
    Simon Chen - Software Engineer
    Languages: C++, Python, Rust, SQL
    Experience: Built low-latency C++ trading pipeline achieving 20µs latency and 100K queries.
    Reduced memory footprint by 45% using lock-free SPSC ring buffers.
    """
    jd = "Looking for a C++ and Python engineer with low-latency and concurrency experience."

    report = evaluate_resume_text(resume, jd)
    assert report.overall_score >= 80
    assert report.role_alignment_score >= 30
    assert report.technical_depth_score >= 20
    assert "c++" in report.matched_keywords
    assert "python" in report.matched_keywords
    assert len(report.extracted_metrics) >= 2


def test_evaluate_resume_text_missing_keywords() -> None:
    resume = "Python web developer using Django and PostgreSQL."
    jd = "Requires Rust, Kubernetes, and Kafka."

    report = evaluate_resume_text(resume, jd)
    assert "rust" in report.missing_keywords
    assert "kubernetes" in report.missing_keywords
    assert any("Consider highlighting" in s for s in report.suggestions)


def test_format_evaluation_report() -> None:
    report = evaluate_resume_text(
        resume_text="C++ developer with 20µs latency optimizations.",
        jd_text="C++ systems developer.",
    )
    formatted = format_evaluation_report(report, target_role="Systems SWE")
    assert "RESUME EVALUATION REPORT: SYSTEMS SWE" in formatted
    assert "Overall Match Score" in formatted
    assert "SCORE BREAKDOWN:" in formatted


def test_evaluate_pdf_against_jd() -> None:
    if not TAILORED_PDF.is_file():
        pytest.skip(f"{TAILORED_PDF} not found")

    jd = "Software Engineer with experience in C++, Python, distributed systems, and performance tuning."
    report = evaluate_pdf_against_jd(TAILORED_PDF, jd)
    assert report.overall_score >= 70
    assert report.gate_compliance_score == 10
