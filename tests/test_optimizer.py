"""Tests for the combinatorial plan optimizer module."""

from __future__ import annotations

from worksisyphus.optimizer import (
    format_optimization_report,
    generate_candidate_plans,
    optimize_plan,
)
from worksisyphus.profile import Profile


def test_generate_candidate_plans_systems(small_profile: Profile) -> None:
    jd_text = "Looking for a low-latency C++ Rust distributed systems engineer."
    candidates = generate_candidate_plans(small_profile, jd_text, role_name="systems_engineer")
    assert len(candidates) >= 1
    for cand in candidates:
        assert "experiences" in cand
        assert "projects" in cand
        assert "skills" in cand


def test_optimize_plan_selects_winner(small_profile: Profile) -> None:
    jd_text = "Python engineer with backend API experience."
    best_plan, best_eval, results = optimize_plan(small_profile, jd_text, role_name="software_engineer")
    assert len(results) >= 1
    assert "total_score" in best_eval
    assert best_eval["total_score"] > 0
    assert "experiences" in best_plan

    report = format_optimization_report(best_plan, best_eval, results)
    assert "HACKERRANK PLAN OPTIMIZER REPORT" in report
    assert "WINNING PLAN CATEGORY BREAKDOWN:" in report
    assert "OPTIMAL PLAN JSON SELECTION:" in report
