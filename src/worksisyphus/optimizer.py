"""Combinatorial plan optimizer: tests multiple content permutations to maximize evaluation score."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .evaluator import evaluate_resume_text, selection_to_plain_text
from .hiring_agent import HackerRankHiringAgent
from .plan import parse_plan
from .profile import Profile


@dataclass(frozen=True)
class CandidatePlanResult:
    plan_dict: dict[str, Any]
    total_score: float
    alignment_score: float
    depth_score: float
    impact_score: float
    summary: str


def generate_candidate_plans(
    profile: Profile,
    jd_text: str,
    role_name: str | None = None,
) -> list[dict[str, Any]]:
    """Generate viable plan permutations adhering to selection guardrails."""
    jd_lower = jd_text.lower()
    candidates: list[dict[str, Any]] = []

    # Detect JD archetype
    is_systems_quant = any(
        k in jd_lower for k in ("c++", "rust", "low-latency", "latency", "quant", "concurrency", "systems", "trading")
    )
    is_frontend_web = any(
        k in jd_lower for k in ("frontend", "react", "next.js", "ui", "css", "web", "full stack", "fullstack")
    )
    is_mobile = "mobile" in jd_lower or "ios" in jd_lower or "android" in jd_lower
    is_civic = "civic" in jd_lower or "food" in jd_lower or "sustainability" in jd_lower
    is_blockchain = "blockchain" in jd_lower or "web3" in jd_lower or "crypto" in jd_lower
    is_it = "it" in jd_lower or "helpdesk" in jd_lower or "support" in jd_lower or "sysadmin" in jd_lower

    # Candidate projects selection based on guardrails
    available_projects = list(profile.projects.keys())

    # Filter guarded projects
    valid_projects = []
    for p in available_projects:
        if p == "personal-website" and not is_frontend_web:
            continue
        if p == "fitness-tracker" and not is_mobile:
            continue
        if p == "spark-food-waste" and not is_civic:
            continue
        if p == "ml-marketplace" and not is_blockchain:
            continue
        valid_projects.append(p)

    # Prioritize Persephone for engineering / systems / quant
    if "persephone" in valid_projects and is_systems_quant:
        valid_projects.remove("persephone")
        valid_projects.insert(0, "persephone")

    # Experience list (respect BU IT gate)
    valid_experiences = []
    for exp_id in profile.experiences.keys():
        if exp_id == "bu-engineering-it" and not is_it:
            continue
        valid_experiences.append(exp_id)

    # Permutation Strategy 1: Top 2 projects, full bullets
    if len(valid_projects) >= 2:
        candidates.append(
            {
                "experiences": {exp_id: "all" for exp_id in valid_experiences},
                "projects": {p: "all" for p in valid_projects[:2]},
                "skills": "all",
            }
        )

    # Permutation Strategy 2: Top 3 projects, full bullets
    if len(valid_projects) >= 3:
        candidates.append(
            {
                "experiences": {exp_id: "all" for exp_id in valid_experiences},
                "projects": {p: "all" for p in valid_projects[:3]},
                "skills": "all",
            }
        )

    # Permutation Strategy 3: Selected high-impact bullets per project
    proj_picks_selective: dict[str, list[str]] = {}
    for p in valid_projects[:3]:
        proj = profile.projects[p]
        b_slugs = list(proj.bullets.keys())
        # Pick top 2 most metric-heavy or systems-heavy bullets
        proj_picks_selective[p] = b_slugs[:2] if len(b_slugs) >= 2 else b_slugs

    candidates.append(
        {
            "experiences": {exp_id: "all" for exp_id in valid_experiences},
            "projects": proj_picks_selective,
            "skills": "all",
        }
    )

    # Permutation Strategy 4: Re-ranked project orders matching JD keywords
    def project_relevance(p_slug: str) -> int:
        proj = profile.projects[p_slug]
        p_text = f"{proj.name} {proj.tech} " + " ".join(proj.bullets.values())
        p_lower = p_text.lower()
        score = 0
        for word in (
            "c++",
            "rust",
            "python",
            "typescript",
            "react",
            "distributed",
            "concurrency",
            "performance",
            "api",
            "database",
        ):
            if word in jd_lower and word in p_lower:
                score += 5
        return score

    sorted_projects = sorted(valid_projects, key=project_relevance, reverse=True)
    if sorted_projects != valid_projects and len(sorted_projects) >= 2:
        candidates.append(
            {
                "experiences": {exp_id: "all" for exp_id in valid_experiences},
                "projects": {p: "all" for p in sorted_projects[:2]},
                "skills": "all",
            }
        )
        if len(sorted_projects) >= 3:
            candidates.append(
                {
                    "experiences": {exp_id: "all" for exp_id in valid_experiences},
                    "projects": {p: "all" for p in sorted_projects[:3]},
                    "skills": "all",
                }
            )

    # Permutation Strategy 5: Tight 1-page balanced budget (2-3 bullets per exp, 2-3 bullets per proj)
    exp_picks_balanced: dict[str, list[str]] = {}
    for exp_id in valid_experiences:
        exp = profile.experiences[exp_id]
        eb_slugs = list(exp.bullets.keys())
        exp_picks_balanced[exp_id] = eb_slugs[:3] if len(eb_slugs) >= 3 else eb_slugs

    if len(valid_projects) >= 2:
        candidates.append(
            {
                "experiences": exp_picks_balanced,
                "projects": proj_picks_selective,
                "skills": "all",
            }
        )

    return candidates


def optimize_plan(
    profile: Profile,
    jd_text: str,
    role_name: str = "software_engineer",
) -> tuple[dict[str, Any], dict[str, Any], list[CandidatePlanResult]]:
    """Test all candidate plan variations and return the highest-scoring plan."""
    candidates = generate_candidate_plans(profile, jd_text, role_name=role_name)
    results: list[CandidatePlanResult] = []

    best_plan = candidates[0]
    best_eval: dict[str, Any] = {}
    best_score = -1.0

    agent = HackerRankHiringAgent(role_name=role_name, jd_text=jd_text)

    for i, cand in enumerate(candidates, start=1):
        try:
            selection = parse_plan(json.dumps(cand), profile)
            plain_text = selection_to_plain_text(selection, profile)

            # Evaluate with JD token matching engine
            jd_eval = evaluate_resume_text(plain_text, jd_text, candidate_name=profile.contact.name)
            # Evaluate with HackerRank rubric
            hr_eval = agent.evaluate(plain_text, candidate_name=profile.contact.name)

            # Combined weighted score (JD Match 50% + HackerRank Rubric 50%)
            combined_score = round(
                (jd_eval.overall_score * 0.5) + ((hr_eval["total_score"] / hr_eval["max_possible"] * 100) * 0.5),
                1,
            )

            projs = list(cand.get("projects", {}).keys())
            summary = f"Variation #{i}: Projects [{', '.join(projs)}]"

            cand_res = CandidatePlanResult(
                plan_dict=cand,
                total_score=combined_score,
                alignment_score=float(jd_eval.role_alignment_score),
                depth_score=float(jd_eval.technical_depth_score),
                impact_score=float(jd_eval.impact_metrics_score),
                summary=summary,
            )
            results.append(cand_res)

            if combined_score > best_score:
                best_score = combined_score
                best_plan = cand
                best_eval = {
                    "jd_evaluation": jd_eval,
                    "hackerrank_evaluation": hr_eval,
                    "combined_score": combined_score,
                }
        except Exception:
            continue

    # Sort results by score descending
    results.sort(key=lambda r: r.total_score, reverse=True)
    return best_plan, best_eval, results


def format_optimization_report(
    best_plan: dict[str, Any],
    best_eval: dict[str, Any],
    results: list[CandidatePlanResult],
) -> str:
    """Format the combinatorial search report with all tested versions and the winning plan."""
    lines = [
        "=" * 68,
        "AUTO-TAILOR PLAN OPTIMIZER REPORT",
        "=" * 68,
        f"Tested {len(results)} distinct candidate plan combinations from profile.json",
        f"Winning Plan Score: {best_eval.get('combined_score', 0):.1f} / 100 pts",
        "-" * 68,
        "CANDIDATE VARIATIONS TESTED:",
    ]

    for rank, res in enumerate(results, start=1):
        marker = "🏆 [WINNER]" if rank == 1 else f"  #{rank}       "
        lines.append(
            f"{marker} Score: {res.total_score:>5.1f}/100 | Alignment: {res.alignment_score:.0f} | Depth: {res.depth_score:.0f} | Impact: {res.impact_score:.0f}"
        )
        lines.append(f"          {res.summary}")

    lines.append("-" * 68)
    lines.append("OPTIMAL PLAN JSON SELECTION:")
    lines.append(json.dumps(best_plan, indent=2))
    lines.append("=" * 68)
    return "\n".join(lines)
