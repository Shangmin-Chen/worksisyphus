"""Tests for the 1:1 HackerRank hiring agent module."""

from __future__ import annotations

import pytest

from worksisyphus.hiring_agent import (
    HackerRankHiringAgent,
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


def test_hackerrank_agent_evaluation() -> None:
    agent = HackerRankHiringAgent(role_name="software_engineering_intern")
    sample_resume = """
    Simon Chen
    Experience: Lead Software Engineer at EZ Esports building distributed real-time platforms.
    Projects: Persephone low-latency Rust/C++ order book engine with 20µs latency and lock-free SPSC queue.
    """
    result = agent.evaluate(sample_resume)
    assert result["total_score"] >= 80
    assert "scores" in result
    assert "open_source" in result["scores"]
    assert "self_projects" in result["scores"]
    assert "production" in result["scores"]
    assert len(result["key_strengths"]) >= 1

    report = format_hackerrank_report(result, role_name="software_engineering_intern")
    assert "HACKERRANK HIRING AGENT SCORECARD" in report
    assert "Open Source" in report
    assert "Self Projects" in report
    assert "Production Experience" in report
