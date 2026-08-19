"""Tests for the 1:1 HackerRank hiring agent module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from worksisyphus.hiring_agent import (
    CategoryScore,
    Deductions,
    HackerRankHiringAgent,
    build_evaluation_model,
    format_hackerrank_report,
    list_roles,
    load_role,
)


def test_list_roles() -> None:
    roles = list_roles()
    assert "software_engineering_intern" in roles
    assert "systems_engineer" in roles
    assert "quant_engineer" in roles


def test_load_role_schema() -> None:
    role = load_role("software_engineering_intern")
    assert role.name == "software_engineering_intern"
    assert len(role.categories) == 3
    assert role.bonus_max == 10
    assert role.max_final_score == 110
    assert "open_source" in [c.key for c in role.categories]


def test_load_invalid_role() -> None:
    with pytest.raises(FileNotFoundError):
        load_role("nonexistent_role_name")


def test_pydantic_models_and_schema_builder() -> None:
    score = CategoryScore(score=30.0, max=35, evidence="GSoC participant")
    assert score.score == 30.0
    assert score.max == 35

    deductions = Deductions(total=5.0, reasons="Grammar issues")
    assert deductions.total == 5.0

    role = load_role("systems_engineer")
    model_cls = build_evaluation_model(role)
    schema = model_cls.model_json_schema()
    assert "properties" in schema
    assert "scores" in schema["properties"]
    assert "bonus_points" in schema["properties"]
    assert "deductions" in schema["properties"]


def test_hackerrank_agent_evaluation_all_roles() -> None:
    sample_resume = """
    Simon Chen
    Experience: Lead Software Engineer at EZ Esports building distributed real-time platforms.
    Projects: Persephone low-latency Rust/C++ order book engine with 20µs latency and lock-free SPSC queue.
    """
    for role_name in ("software_engineering_intern", "systems_engineer", "quant_engineer"):
        agent = HackerRankHiringAgent(role_name=role_name)
        result = agent.evaluate(sample_resume)
        assert result["total_score"] >= 80
        assert "scores" in result
        assert len(result["scores"]) == 3
        report = format_hackerrank_report(result, role_name=role_name)
        assert "HACKERRANK HIRING AGENT SCORECARD" in report
        assert "CATEGORY SCORE BREAKDOWN:" in report


def test_hackerrank_report_with_deductions() -> None:
    eval_data = {
        "total_score": 75.0,
        "max_possible": 100,
        "role_title": "Software Intern",
        "scores": {
            "open_source": {"score": 25.0, "max": 35, "evidence": "Good repos"},
            "self_projects": {"score": 25.0, "max": 30, "evidence": "Solid projects"},
            "production": {"score": 30.0, "max": 35, "evidence": "Production apps"},
        },
        "bonus_points": {"total": 5.0, "breakdown": "Extra metrics"},
        "deductions": {"total": 10.0, "reasons": "Formatting discrepancies"},
        "key_strengths": ["Strong systems fundamentals"],
        "areas_for_improvement": ["Add more tests"],
    }
    report = format_hackerrank_report(eval_data, role_name="software_engineering_intern")
    assert "⚠️ Deductions:            -10.0 pts (Formatting discrepancies)" in report
    assert "🎁 Bonus Points:          +5.0 pts (Extra metrics)" in report
    assert "Strong systems fundamentals" in report
    assert "Add more tests" in report


def test_hackerrank_agent_llm_call_gemini(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "scores": {
                                "open_source": {"score": 30.0, "max": 35, "evidence": "Strong OSS"},
                                "self_projects": {"score": 28.0, "max": 30, "evidence": "Low latency"},
                                "production": {"score": 32.0, "max": 35, "evidence": "Production scale"},
                            },
                            "bonus_points": {"total": 5.0, "breakdown": "Benchmarks"},
                            "deductions": {"total": 0.0, "reasons": "None"},
                            "key_strengths": ["Systems engineering"],
                            "areas_for_improvement": ["Open source"],
                        }
                    )
                }
            }
        ]
    }
    fake_response.raise_for_status = MagicMock()

    import requests

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: fake_response)

    agent = HackerRankHiringAgent(role_name="software_engineering_intern")
    result = agent.evaluate("Sample resume text")
    assert result["total_score"] == 95.0
    assert result["scores"]["open_source"]["score"] == 30.0
