"""Tests for the combinatorial plan optimizer module."""

from __future__ import annotations

import pytest

from worksisyphus.evaluator import selection_to_plain_text
from worksisyphus.optimizer import (
    OptimizerError,
    format_optimization_report,
    generate_candidate_plans,
    optimize_plan,
)
from worksisyphus.profile import Contact, Education, Experience, Profile, Project


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


def test_guardrail_keywords_match_whole_tokens_only(real_profile: Profile) -> None:
    """Substring matching would fire 'ui' inside 'building' and open the personal-website gate."""
    generic_jd = "You will be building products end to end, gathering requirements from customers."
    candidates = generate_candidate_plans(real_profile, generic_jd, role_name="software_engineer")
    all_projects = {p for c in candidates for p in c.get("projects", {})}
    assert "personal-website" not in all_projects


def test_persephone_outranks_weak_project_on_engineering_jd(real_profile: Profile) -> None:
    """A backend JD that merely mentions mobile must not surface fitness-tracker as filler."""
    jd = "Backend distributed systems engineer serving mobile clients at scale."
    candidates = generate_candidate_plans(real_profile, jd, role_name="software_engineer")
    for cand in candidates:
        projects = list(cand.get("projects", {}).keys())
        assert "fitness-tracker" not in projects
        if projects:
            assert projects[0] == "persephone"


def _degenerate_profile(projects: dict[str, Project], experiences: dict[str, Experience]) -> Profile:
    """A profile with fewer than 2 projects, to exercise the optimizer's degenerate branch."""
    return Profile(
        contact=Contact(name="Simon Chen", email="s@example.com", phone="555-0100"),
        education=(Education("BU", "Boston, MA", "BA CS", "2026", ("Systems",)),),
        experiences=experiences,
        projects=projects,
        skills={"languages": ("Python", "Rust")},
    )


def test_optimize_plan_raises_when_no_candidate_scores(small_profile: Profile, monkeypatch) -> None:
    """A total scoring failure must never return candidates[0] as though it had won.

    `apply` without --plan turns optimize_plan's winner straight into a delivered resume, so an
    unscored, unranked plan reaching the caller is a silent fallback, not a graceful degradation.
    """

    def boom(*_args, **_kwargs):
        raise RuntimeError("scorer exploded")

    monkeypatch.setattr("worksisyphus.optimizer.selection_to_plain_text", boom)

    with pytest.raises(OptimizerError) as exc_info:
        optimize_plan(small_profile, "Python backend engineer.", role_name="software_engineer")

    message = str(exc_info.value)
    assert "refusing to return an unranked plan" in message
    assert "RuntimeError" in message
    assert "scorer exploded" in message


def test_optimize_plan_surfaces_partial_failures(small_profile: Profile, monkeypatch, capsys) -> None:
    """When some candidates fail the search space shrinks; that must be reported, not swallowed."""
    real = selection_to_plain_text
    calls = {"n": 0}

    def flaky(selection, profile):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("candidate 1 is broken")
        return real(selection, profile)

    candidate_count = len(generate_candidate_plans(small_profile, "Python backend engineer."))
    assert candidate_count >= 2, "test needs at least one surviving candidate"

    monkeypatch.setattr("worksisyphus.optimizer.selection_to_plain_text", flaky)
    best_plan, best_eval, results = optimize_plan(small_profile, "Python backend engineer.")

    assert len(results) == candidate_count - 1
    failures = best_eval["candidate_failures"]
    assert failures["failed"] == 1
    assert failures["total"] == candidate_count
    assert failures["errors"]["ValueError"]["count"] == 1
    assert "candidate 1 is broken" in failures["errors"]["ValueError"]["example"]

    # Also on stderr: plan-less `apply` (cli.py) discards best_eval and results entirely.
    assert "scored only" in capsys.readouterr().err

    report = format_optimization_report(best_plan, best_eval, results)
    assert "WARNING:" in report
    assert "ValueError x1" in report


def test_degenerate_single_project_path_respects_guardrails() -> None:
    """The <2-projects branch must not be a back door for gated slugs."""
    profile = _degenerate_profile(
        projects={"personal-website": Project("personal-website", "Site", "Next.js", "2025", {"w1": "Built a site"})},
        experiences={
            "bu-engineering-it": Experience("bu-engineering-it", "Tech", "BU IT", "MA", "2024", {"i1": "Fixed PCs"}),
            "org-a": Experience("org-a", "Engineer", "OrgA", "NY", "2025", {"a1": "Wrote a kernel bypass path"}),
        },
    )
    jd = "Low-latency kernel networking C++ systems engineer."

    candidates = generate_candidate_plans(profile, jd, role_name="systems_engineer")
    assert candidates, "degenerate profile must still yield a candidate"
    for cand in candidates:
        assert "personal-website" not in cand["projects"]
        assert "bu-engineering-it" not in cand["experiences"]
        assert "org-a" in cand["experiences"]

    best_plan, _best_eval, _results = optimize_plan(profile, jd, role_name="systems_engineer")
    assert "personal-website" not in best_plan["projects"]
    assert "bu-engineering-it" not in best_plan["experiences"]


def test_degenerate_path_raises_when_guardrails_leave_nothing() -> None:
    """Every entry gated out means no guardrail-compliant plan exists; raise instead of emitting one."""
    profile = _degenerate_profile(
        projects={"fitness-tracker": Project("fitness-tracker", "Fit", "Swift", "2025", {"f1": "Tracked runs"})},
        experiences={
            "bu-engineering-it": Experience("bu-engineering-it", "Tech", "BU IT", "MA", "2024", {"i1": "Fixed PCs"})
        },
    )

    with pytest.raises(OptimizerError) as exc_info:
        generate_candidate_plans(profile, "Low-latency kernel C++ systems engineer.", role_name="systems_engineer")
    assert "guardrails" in str(exc_info.value)
