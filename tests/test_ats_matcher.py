"""Tests for deterministic ATS keyword extraction and matching engine."""

from __future__ import annotations

from worksisyphus.core.domain.ats_matcher import (
    ATSKeywordMatchResult,
    extract_keywords,
    score_ats_keywords,
)


def test_extract_keywords_empty() -> None:
    assert extract_keywords("") == ()
    assert extract_keywords("   ") == ()


def test_extract_keywords_technical_stack() -> None:
    jd_text = """
    We are seeking a Senior Backend Engineer with deep experience in Python, C++17,
    and distributed systems. You should be familiar with Kubernetes, Docker, and
    low-latency event streaming.
    """
    keywords = extract_keywords(jd_text)
    expected = {
        "backend",
        "python",
        "c++17",
        "distributed systems",
        "distributed",
        "kubernetes",
        "docker",
        "low-latency",
        "streaming",
    }
    assert expected.issubset(set(keywords))


def test_score_ats_keywords_no_jd_terms() -> None:
    res = score_ats_keywords("Built high performance service", "Looking for enthusiastic person")
    assert res.coverage_score == 100.0
    assert res.matched_keywords == ()
    assert res.missing_keywords == ()


def test_score_ats_keywords_exact_matches() -> None:
    jd_text = "Required: Python, Docker, Redis, Postgres."
    resume_text = "Experienced in Python, Docker, and Redis for data processing."

    result = score_ats_keywords(resume_text, jd_text)
    assert "python" in result.matched_keywords
    assert "docker" in result.matched_keywords
    assert "redis" in result.matched_keywords
    assert "postgres" in result.missing_keywords
    assert result.coverage_score == 75.0


def test_score_ats_keywords_synonym_expansion() -> None:
    # JD asks for kubernetes and low-latency, resume uses k8s and low latency
    jd_text = "Must have experience with Kubernetes and low-latency systems."
    resume_text = "Architected low latency infrastructure deployed on k8s clusters."

    result = score_ats_keywords(resume_text, jd_text)
    assert "kubernetes" in result.matched_keywords
    assert "low-latency" in result.matched_keywords
    assert "kubernetes" not in result.missing_keywords
    assert "low-latency" not in result.missing_keywords


def test_ats_keyword_match_result_as_meta() -> None:
    result = ATSKeywordMatchResult(
        coverage_score=85.714,
        matched_keywords=("python", "docker", "redis"),
        missing_keywords=("postgres",),
        jd_keywords=("python", "docker", "redis", "postgres"),
    )
    meta = result.as_meta()
    assert meta["coverage_score"] == 85.7
    assert meta["matched_keywords"] == ["python", "docker", "redis"]
    assert meta["missing_keywords"] == ["postgres"]
    assert meta["total_jd_keywords"] == 4
    assert meta["matched_count"] == 3
