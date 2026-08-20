"""Plan optimizer powered by HackerRank role rubrics and candidate evaluation engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .evaluator import selection_to_plain_text
from .hiring_agent import HackerRankHiringAgent
from .plan import parse_plan
from .profile import Profile


@dataclass(frozen=True)
class CandidatePlanResult:
    plan_dict: dict[str, Any]
    total_score: float
    max_possible: int
    scores: dict[str, Any]
    bonus_points: float
    summary: str


def rank_projects_by_hackerrank_rubric(
    profile: Profile,
    agent: HackerRankHiringAgent,
) -> list[tuple[str, float]]:
    """Score and rank every project in profile.json using the HackerRank evaluation engine."""
    scored_projects: list[tuple[str, float]] = []
    for slug, proj in profile.projects.items():
        proj_text = f"{proj.name} {proj.tech}\n" + "\n".join(f"- {b}" for b in proj.bullets.values())
        eval_result = agent.evaluate(proj_text, candidate_name=profile.contact.name)
        score = float(eval_result.get("total_score", 0.0))
        scored_projects.append((slug, score))

    scored_projects.sort(key=lambda item: item[1], reverse=True)
    return scored_projects


def rank_bullets_by_hackerrank_rubric(
    bullets: dict[str, str],
    profile: Profile,
    agent: HackerRankHiringAgent,
) -> list[str]:
    """Score and sort bullet slugs within an entry in descending order of HackerRank rubric value."""
    scored_bullets: list[tuple[str, float]] = []
    for b_slug, b_text in bullets.items():
        eval_result = agent.evaluate(b_text, candidate_name=profile.contact.name)
        score = float(eval_result.get("total_score", 0.0))
        scored_bullets.append((b_slug, score))

    scored_bullets.sort(key=lambda item: item[1], reverse=True)
    return [b[0] for b in scored_bullets]


def generate_candidate_plans(
    profile: Profile,
    jd_text: str,
    role_name: str = "software_engineer",
) -> list[dict[str, Any]]:
    """Dynamically generate candidate plan variations sorted by HackerRank rubric score."""
    agent = HackerRankHiringAgent(role_name=role_name, jd_text=jd_text)

    # 1. Rank all projects dynamically by HackerRank rubric value
    ranked_projects = [p[0] for p in rank_projects_by_hackerrank_rubric(profile, agent)]

    # 2. Sort bullets in each experience by HackerRank rubric score
    sorted_exp_bullets: dict[str, list[str]] = {}
    for exp_slug, exp in profile.experiences.items():
        sorted_exp_bullets[exp_slug] = rank_bullets_by_hackerrank_rubric(exp.bullets, profile, agent)

    # 3. Sort bullets in each project by HackerRank rubric score
    sorted_proj_bullets: dict[str, list[str]] = {}
    for proj_slug, proj in profile.projects.items():
        sorted_proj_bullets[proj_slug] = rank_bullets_by_hackerrank_rubric(proj.bullets, profile, agent)

    candidates: list[dict[str, Any]] = []

    # Variation A: Top 2 HackerRank-ranked projects with sorted bullets
    if len(ranked_projects) >= 2:
        top_2 = ranked_projects[:2]
        candidates.append(
            {
                "experiences": {exp_slug: sorted_exp_bullets[exp_slug] for exp_slug in profile.experiences},
                "projects": {p_slug: sorted_proj_bullets[p_slug] for p_slug in top_2},
                "skills": "all",
            }
        )

    # Variation B: Top 3 HackerRank-ranked projects with sorted bullets
    if len(ranked_projects) >= 3:
        top_3 = ranked_projects[:3]
        candidates.append(
            {
                "experiences": {exp_slug: sorted_exp_bullets[exp_slug] for exp_slug in profile.experiences},
                "projects": {p_slug: sorted_proj_bullets[p_slug] for p_slug in top_3},
                "skills": "all",
            }
        )

    # Variation C: Lean high-signal variation (Top 2-3 bullets per experience, top 2-3 bullets per project)
    if len(ranked_projects) >= 2:
        top_2 = ranked_projects[:2]
        lean_exp = {exp_slug: sorted_exp_bullets[exp_slug][:3] for exp_slug in profile.experiences}
        lean_proj = {p_slug: sorted_proj_bullets[p_slug][:2] for p_slug in top_2}
        candidates.append(
            {
                "experiences": lean_exp,
                "projects": lean_proj,
                "skills": "all",
            }
        )

    # Variation D: Full depth with top-ranked project prominence
    if len(ranked_projects) >= 1:
        candidates.append(
            {
                "experiences": {exp_slug: "all" for exp_slug in profile.experiences},
                "projects": {p_slug: "all" for p_slug in ranked_projects[:2]},
                "skills": "all",
            }
        )

    # Fallback Variation: All experiences, all projects, all skills
    if not candidates:
        candidates.append(
            {
                "experiences": {exp_slug: "all" for exp_slug in profile.experiences},
                "projects": {p_slug: "all" for p_slug in profile.projects},
                "skills": "all",
            }
        )

    return candidates


def optimize_plan(
    profile: Profile,
    jd_text: str,
    role_name: str = "software_engineer",
) -> tuple[dict[str, Any], dict[str, Any], list[CandidatePlanResult]]:
    """Test all candidate variations against HackerRank rubric and return the winning plan."""
    agent = HackerRankHiringAgent(role_name=role_name, jd_text=jd_text)
    candidates = generate_candidate_plans(profile, jd_text, role_name=role_name)
    results: list[CandidatePlanResult] = []

    best_plan = candidates[0]
    best_eval: dict[str, Any] = {
        "role_title": agent.role.position_title,
        "total_score": 0.0,
        "max_possible": agent.role.max_final_score,
        "scores": {},
    }
    best_score = -1.0

    for i, cand in enumerate(candidates, start=1):
        try:
            selection = parse_plan(json.dumps(cand), profile)
            plain_text = selection_to_plain_text(selection, profile)

            # Pure HackerRank rubric evaluation
            hr_eval = agent.evaluate(plain_text, candidate_name=profile.contact.name)
            total_score = float(hr_eval.get("total_score", 0.0))
            max_possible = int(hr_eval.get("max_possible", 100))
            bonus = float(hr_eval.get("bonus_points", {}).get("total", 0.0))

            projs = list(cand.get("projects", {}).keys())
            summary = f"Variation #{i}: Projects [{', '.join(projs)}]"

            cand_res = CandidatePlanResult(
                plan_dict=cand,
                total_score=total_score,
                max_possible=max_possible,
                scores=hr_eval.get("scores", {}),
                bonus_points=bonus,
                summary=summary,
            )
            results.append(cand_res)

            if total_score > best_score:
                best_score = total_score
                best_plan = cand
                best_eval = hr_eval
        except Exception:
            continue

    results.sort(key=lambda r: r.total_score, reverse=True)
    return best_plan, best_eval, results


def format_optimization_report(
    best_plan: dict[str, Any],
    best_eval: dict[str, Any],
    results: list[CandidatePlanResult],
) -> str:
    """Format the HackerRank-powered optimization report and optimal plan."""
    role_title = best_eval.get("role_title", "Software Engineer")
    total_score = best_eval.get("total_score", 0.0)
    max_possible = best_eval.get("max_possible", 110)

    lines = [
        "=" * 68,
        f"HACKERRANK PLAN OPTIMIZER REPORT: {role_title.upper()}",
        "=" * 68,
        f"Evaluated {len(results)} candidate plan variations using HackerRank role rubric",
        f"Winning Plan Score: {total_score:.1f} / {max_possible} points",
        "-" * 68,
        "CANDIDATE VARIATIONS TESTED:",
    ]

    for rank, res in enumerate(results, start=1):
        marker = "🏆 [WINNER]" if rank == 1 else f"  #{rank}       "
        lines.append(
            f"{marker} Score: {res.total_score:>5.1f} / {res.max_possible} pts | Bonus: +{res.bonus_points:.1f} pts"
        )
        lines.append(f"          {res.summary}")

    lines.append("-" * 68)
    lines.append("WINNING PLAN CATEGORY BREAKDOWN:")
    for key, cat_data in best_eval.get("scores", {}).items():
        score = cat_data.get("score", 0)
        max_score = cat_data.get("max", 0)
        evidence = cat_data.get("evidence", "")
        lines.append(f"  • {key.replace('_', ' ').title():<30} {score:>4.1f} / {max_score} pts")
        if evidence:
            lines.append(f"    Evidence: {evidence}")

    lines.append("-" * 68)
    lines.append("OPTIMAL PLAN JSON SELECTION:")
    lines.append(json.dumps(best_plan, indent=2))
    lines.append("=" * 68)
    return "\n".join(lines)
