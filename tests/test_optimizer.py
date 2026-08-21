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
    assert "HACKERRANK KNAPSACK OPTIMIZER REPORT" in report
    assert "WINNING PLAN CATEGORY BREAKDOWN:" in report
    assert "OPTIMAL PLAN JSON SELECTION" in report


def test_optimize_plan_with_real_profile(real_profile: Profile) -> None:
    jd_text = "Looking for a Distributed Systems Engineer with C++, Python, and low-latency concurrency."
    candidates = generate_candidate_plans(real_profile, jd_text, role_name="systems_engineer")
    assert len(candidates) >= 3

    best_plan, best_eval, results = optimize_plan(real_profile, jd_text, role_name="systems_engineer")
    assert len(results) >= 3
    assert best_eval["total_score"] >= 80
    assert "persephone" in best_plan["projects"]


def test_optimizer_enforces_selection_guardrails(real_profile: Profile) -> None:
    # Systems role: persephone must be first, personal-website / fitness-tracker / BU-IT must be filtered
    systems_jd = "Low-latency systems and kernel networking C++ engineer."
    candidates = generate_candidate_plans(real_profile, systems_jd, role_name="systems_engineer")
    for cand in candidates:
        proj_list = list(cand.get("projects", {}).keys())
        if proj_list:
            assert proj_list[0] == "persephone"
            assert "personal-website" not in proj_list
            assert "fitness-tracker" not in proj_list
            assert "spark-food-waste" not in proj_list
        exp_list = list(cand.get("experiences", {}).keys())
        assert "bu-engineering-it" not in exp_list

    # Mobile role: fitness-tracker allowed
    mobile_jd = "Senior iOS / Swift mobile developer building fitness mobile apps."
    mobile_candidates = generate_candidate_plans(real_profile, mobile_jd, role_name="software_engineer")
    all_mobile_projs = {p for c in mobile_candidates for p in c.get("projects", {})}
    assert "fitness-tracker" in all_mobile_projs
