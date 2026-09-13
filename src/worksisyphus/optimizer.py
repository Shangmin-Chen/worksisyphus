"""Marginal Knapsack & Line-Budgeted Plan Optimizer powered by HackerRank role rubrics."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .evaluator import selection_to_plain_text
from .hiring_agent import HackerRankHiringAgent
from .plan import parse_plan
from .profile import Profile
from .selection import MIN_BULLETS

# Physical vertical line budgeting for Jake's 1-page LaTeX template:
# Total Page Budget ≈ 46 lines.
# Fixed overhead: Header (4 lines), Education (3 lines), Skills (4 lines), Section Headers (3 lines) = ~14 lines.
# Available budget for Experience + Projects = 32 to 36 lines.
MAX_EXPERIENCE_PROJECT_LINES = 35.0
# Tighter budget used by the "guaranteed zero-trim safety" strategy: packs fewer bullets so the
# trim loop should never need to fire even after the renderer's own line-height rounding.
COMPACT_EXPERIENCE_PROJECT_LINES = 32.0
HEADER_LINE_COST = 1.5  # Header cost per experience / project entry


class OptimizerError(RuntimeError):
    """The optimizer could not produce a plan it actually scored and ranked.

    Raised instead of returning an unranked candidate: a plan-less `apply` feeds the
    optimizer's winner straight into a delivered resume, so "we could not rank anything"
    must stop the pipeline rather than silently pick an arbitrary configuration.
    """


@dataclass(frozen=True)
class ScoredBullet:
    slug: str
    text: str
    score: float
    lines: float
    density: float


@dataclass(frozen=True)
class ScoredEntry:
    slug: str
    title: str
    is_project: bool
    bullets: list[ScoredBullet]
    header_score: float
    total_score: float


def estimate_bullet_lines(text: str) -> float:
    """Estimate rendered LaTeX line height for a resume bullet."""
    length = len(text.strip())
    if length <= 100:
        return 1.0
    elif length <= 200:
        return 2.0
    else:
        return 3.0


def score_bullet(
    slug: str,
    text: str,
    profile: Profile,
    agent: HackerRankHiringAgent,
) -> ScoredBullet:
    """Compute HackerRank rubric value and line-density for an individual bullet."""
    eval_result = agent.evaluate(text, candidate_name=profile.contact.name)
    score = float(eval_result.get("total_score", 0.0))
    lines = estimate_bullet_lines(text)
    density = score / lines if lines > 0 else 0.0
    return ScoredBullet(slug=slug, text=text, score=score, lines=lines, density=density)


def score_and_rank_entries(
    profile: Profile,
    agent: HackerRankHiringAgent,
) -> tuple[list[ScoredEntry], list[ScoredEntry]]:
    """Score all experiences and projects, sorting bullets internally by descending HackerRank score."""
    scored_experiences: list[ScoredEntry] = []
    for exp_slug, exp in profile.experiences.items():
        bullets = [score_bullet(b_slug, b_text, profile, agent) for b_slug, b_text in exp.bullets.items()]
        bullets.sort(key=lambda b: b.score, reverse=True)
        exp_text = f"{exp.role} {exp.org}"
        header_eval = agent.evaluate(exp_text, candidate_name=profile.contact.name)
        header_score = float(header_eval.get("total_score", 0.0))
        total_score = header_score + sum(b.score for b in bullets)
        scored_experiences.append(
            ScoredEntry(
                slug=exp_slug,
                title=f"{exp.role} at {exp.org}",
                is_project=False,
                bullets=bullets,
                header_score=header_score,
                total_score=total_score,
            )
        )

    scored_projects: list[ScoredEntry] = []
    for proj_slug, proj in profile.projects.items():
        bullets = [score_bullet(b_slug, b_text, profile, agent) for b_slug, b_text in proj.bullets.items()]
        bullets.sort(key=lambda b: b.score, reverse=True)
        proj_text = f"{proj.name} {proj.tech}"
        header_eval = agent.evaluate(proj_text, candidate_name=profile.contact.name)
        header_score = float(header_eval.get("total_score", 0.0))
        total_score = header_score + sum(b.score for b in bullets)
        scored_projects.append(
            ScoredEntry(
                slug=proj_slug,
                title=f"{proj.name} ({proj.tech})",
                is_project=True,
                bullets=bullets,
                header_score=header_score,
                total_score=total_score,
            )
        )

    # Sort projects descending by aggregate HackerRank value
    scored_projects.sort(key=lambda p: p.total_score, reverse=True)
    return scored_experiences, scored_projects


def solve_line_budget_knapsack(
    experiences: list[ScoredEntry],
    selected_projects: list[ScoredEntry],
    max_lines: float = MAX_EXPERIENCE_PROJECT_LINES,
) -> tuple[dict[str, list[str]], dict[str, list[str]], float]:
    """Greedily pack highest-density bullets within line capacity.

    Allocates up to MIN_BULLETS bullets per chosen entry and skips entries with none: a
    bullet-less entry would still burn HEADER_LINE_COST of budget and, downstream, make
    plan.py reject the whole candidate with "No bullets selected for ...".
    """
    total_lines = 0.0
    exp_picks: dict[str, list[str]] = {}
    proj_picks: dict[str, list[str]] = {}

    # 1. Base cost: allocate headers and top MIN_BULLETS mandatory bullets for each chosen entry
    skipped = [e for e in experiences + selected_projects if not e.bullets]
    for entry in skipped:
        print(
            f"WARN: knapsack skipping {entry.slug!r}: no bullets selected "
            "(entry would fail plan validation downstream)",
            file=sys.stderr,
        )
    active_entries = [e for e in experiences + selected_projects if e.bullets]
    for entry in active_entries:
        total_lines += HEADER_LINE_COST
        min_bullets = entry.bullets[:MIN_BULLETS] if len(entry.bullets) >= MIN_BULLETS else entry.bullets
        chosen_slugs = [b.slug for b in min_bullets]
        total_lines += sum(b.lines for b in min_bullets)

        if entry.is_project:
            proj_picks[entry.slug] = chosen_slugs
        else:
            exp_picks[entry.slug] = chosen_slugs

    # 2. Pool of remaining optional bullets across all active entries
    remaining_pool: list[tuple[ScoredBullet, ScoredEntry]] = []
    for entry in active_entries:
        chosen_set = set(proj_picks.get(entry.slug, []) if entry.is_project else exp_picks.get(entry.slug, []))
        for b in entry.bullets:
            if b.slug not in chosen_set:
                remaining_pool.append((b, entry))

    # Sort remaining pool by density (value per line), breaking ties deterministically by score
    # then slug rather than relying on Python's stable sort plus dict insertion order.
    remaining_pool.sort(key=lambda item: (-item[0].density, -item[0].score, item[1].slug, item[0].slug))

    # 3. Pack highest-density bullets until capacity is reached
    for bullet, entry in remaining_pool:
        if total_lines + bullet.lines <= max_lines:
            total_lines += bullet.lines
            if entry.is_project:
                proj_picks[entry.slug].append(bullet.slug)
            else:
                exp_picks[entry.slug].append(bullet.slug)

    return exp_picks, proj_picks, total_lines


IT_KEYWORDS = ("it support", "desktop support", "it technician", "help desk", "it specialist", "sysadmin")
MOBILE_KEYWORDS = ("mobile", "ios", "android", "swift", "swiftui", "react native", "flutter")
CIVIC_KEYWORDS = ("civic", "food waste", "sustainability", "climate", "non-profit", "social impact")
CRYPTO_KEYWORDS = (
    "blockchain",
    "web3",
    "crypto",
    "cryptocurrency",
    "smart contract",
    "ethereum",
    "solana",
    "defi",
)
FRONTEND_KEYWORDS = (
    "frontend",
    "front-end",
    "ui",
    "ux",
    "react",
    "next.js",
    "full stack",
    "fullstack",
    "web",
    "edge",
    "serverless",
)
SYSTEMS_QUANT_KEYWORDS = (
    "quant",
    "quantitative",
    "systems",
    "infra",
    "infrastructure",
    "low-latency",
    "c++",
    "kernel",
    "trading",
    "embedded",
    "networking",
)
ENGINEERING_KEYWORDS = ("backend", "distributed", "performance", "systems", "infra", "concurrency", "low-latency")

# Gated slugs, named so a profile.json rename can never silently disable a guardrail with no error
# (see test_gated_slugs_exist_in_the_real_profile in tests/test_optimizer.py).
BU_IT_SLUG = "bu-engineering-it"
PERSEPHONE_SLUG = "persephone"
MOBILE_PROJECT_SLUG = "fitness-tracker"
CIVIC_PROJECT_SLUG = "spark-food-waste"
CRYPTO_PROJECT_SLUG = "ml-marketplace"
PERSONAL_WEBSITE_SLUG = "personal-website"
GUARDED_SLUGS = (
    BU_IT_SLUG,
    PERSEPHONE_SLUG,
    MOBILE_PROJECT_SLUG,
    CIVIC_PROJECT_SLUG,
    CRYPTO_PROJECT_SLUG,
    PERSONAL_WEBSITE_SLUG,
)


def _text_match_variants(text: str) -> tuple[str, ...]:
    """Lowercase spellings to compare against hyphen/space/underscore role titles.

    Apply-style titles like ``Front-End Engineer`` normalize to ``front end engineer`` when
    separators become spaces, which would miss keyword ``front-end`` without also checking
    hyphenated and original forms.
    """
    lower = text.lower()
    spaced = re.sub(r"[_\-]+", " ", lower)
    hyphened = re.sub(r"[\s_]+", "-", lower).strip("-")
    return tuple(dict.fromkeys(v for v in (lower, spaced, hyphened) if v))


def _mentions_literal(text_lower: str, keywords: tuple[str, ...]) -> bool:
    """Whole-token keyword search on literal lowercased JD text.

    Plain substring matching is unusable here: 'ui' occurs inside 'building', 'ux' inside
    'luxury', 'quant' inside 'quantify'. Word boundaries are expressed with alphanumeric
    lookarounds rather than \\b so that keywords ending in punctuation ('c++', 'next.js')
    still match. Separator variants are not applied — synthesizing hyphens from spaced JD
    prose (e.g. ``low latency customer support`` -> ``low-latency``) would false-positive.
    """
    return any(re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", text_lower) for kw in keywords)


def _mentions_role(role_name: str, keywords: tuple[str, ...]) -> bool:
    """Whole-token keyword search with separator variants for role titles.

    Apply-style titles like ``Front-End Engineer`` normalize to spaced forms that miss
    hyphenated keywords unless hyphenated and original forms are also checked.
    """
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", variant)
        for variant in _text_match_variants(role_name)
        for kw in keywords
    )


def _promote(entries: list[ScoredEntry], slug: str) -> list[ScoredEntry]:
    """Move the named slug to the front, preserving the relative order of everything else."""
    if not any(e.slug == slug for e in entries):
        return entries
    return [e for e in entries if e.slug == slug] + [e for e in entries if e.slug != slug]


def apply_selection_guardrails(
    experiences: list[ScoredEntry],
    projects: list[ScoredEntry],
    jd_text: str,
    role_name: str,
) -> tuple[list[ScoredEntry], list[ScoredEntry]]:
    """Enforce Simon's selection guardrails deterministically."""
    jd_lower = jd_text.lower()

    # 1. BU IT gate: only selected for IT/support/security roles
    is_it_role = _mentions_literal(jd_lower, IT_KEYWORDS) or _mentions_role(role_name, IT_KEYWORDS)
    filtered_exp = [e for e in experiences if e.slug != BU_IT_SLUG or is_it_role]

    jd_is_systems_quant = _mentions_literal(jd_lower, SYSTEMS_QUANT_KEYWORDS)
    jd_is_engineering = jd_is_systems_quant or _mentions_literal(jd_lower, ENGINEERING_KEYWORDS)
    is_systems_quant = jd_is_systems_quant or _mentions_role(role_name, SYSTEMS_QUANT_KEYWORDS)
    is_engineering = is_systems_quant or jd_is_engineering or _mentions_role(role_name, ENGINEERING_KEYWORDS)

    # 2. Weak-project gate. The rule is "the JD *is* a mobile / civic / blockchain role", not
    #    "the JD mentions the word" -- a backend posting that happens to say "mobile clients" must
    #    not admit fitness-tracker as filler. The role title is the strongest signal, so it can
    #    admit a domain even when the posting also reads as engineering-heavy. Only JD-derived
    #    engineering suppresses JD domain keywords; a backend role title must not block a civic JD.
    def _is_role(keywords: tuple[str, ...]) -> bool:
        return _mentions_role(role_name, keywords) or (_mentions_literal(jd_lower, keywords) and not jd_is_engineering)

    has_mobile = _is_role(MOBILE_KEYWORDS)
    has_civic = _is_role(CIVIC_KEYWORDS)
    has_crypto = _is_role(CRYPTO_KEYWORDS)

    # 3. Personal-website gate: frontend/fullstack/web-infra/edge only; never quant/systems/infra.
    # A frontend role title alone cannot override an engineering JD — the posting must also
    # signal frontend/fullstack work, or personal-website weakens backend/systems resumes.
    jd_has_frontend = _mentions_literal(jd_lower, FRONTEND_KEYWORDS)
    is_frontend_web = jd_has_frontend or _mentions_role(role_name, FRONTEND_KEYWORDS)
    allow_personal_website = is_frontend_web and not is_systems_quant and not (is_engineering and not jd_has_frontend)

    filtered_proj = [
        p
        for p in projects
        if (p.slug != MOBILE_PROJECT_SLUG or has_mobile)
        and (p.slug != CIVIC_PROJECT_SLUG or has_civic)
        and (p.slug != CRYPTO_PROJECT_SLUG or has_crypto)
        and (p.slug != PERSONAL_WEBSITE_SLUG or allow_personal_website)
    ]

    # 4. Ranking. Persephone-first outranks weak-project promotion: an engineering JD that merely
    #    mentions mobile must not surface fitness-tracker above persephone. Weak projects lead only
    #    when the JD is not an engineering role at all.
    if is_engineering:
        filtered_proj = _promote(filtered_proj, PERSEPHONE_SLUG)
    elif has_mobile:
        filtered_proj = _promote(filtered_proj, MOBILE_PROJECT_SLUG)
    elif has_civic:
        filtered_proj = _promote(filtered_proj, CIVIC_PROJECT_SLUG)
    elif has_crypto:
        filtered_proj = _promote(filtered_proj, CRYPTO_PROJECT_SLUG)

    return filtered_exp, filtered_proj


def generate_candidate_plans(
    profile: Profile,
    jd_text: str,
    role_name: str = "software_engineer",
) -> list[dict[str, Any]]:
    """Generate line-budgeted candidate plans using the knapsack solver."""
    agent = HackerRankHiringAgent(role_name=role_name, jd_text=jd_text)
    experiences, projects = score_and_rank_entries(profile, agent)
    experiences, projects = apply_selection_guardrails(experiences, projects, jd_text, role_name)

    candidates: list[dict[str, Any]] = []

    # Strategy 1: Top 2 Projects + Knapsack packed to MAX_EXPERIENCE_PROJECT_LINES
    if len(projects) >= 2:
        exp_p, proj_p, lines = solve_line_budget_knapsack(
            experiences, projects[:2], max_lines=MAX_EXPERIENCE_PROJECT_LINES
        )
        candidates.append({"experiences": exp_p, "projects": proj_p, "skills": "all", "_lines": lines})

    # Strategy 2: Top 3 Projects + Knapsack packed to MAX_EXPERIENCE_PROJECT_LINES
    if len(projects) >= 3:
        exp_p, proj_p, lines = solve_line_budget_knapsack(
            experiences, projects[:3], max_lines=MAX_EXPERIENCE_PROJECT_LINES
        )
        candidates.append({"experiences": exp_p, "projects": proj_p, "skills": "all", "_lines": lines})

    # Strategy 3: Tight Compact Knapsack for guaranteed zero-trim safety
    if len(projects) >= 2:
        exp_p, proj_p, lines = solve_line_budget_knapsack(
            experiences, projects[:2], max_lines=COMPACT_EXPERIENCE_PROJECT_LINES
        )
        candidates.append({"experiences": exp_p, "projects": proj_p, "skills": "all", "_lines": lines})

    # Degenerate profile (fewer than 2 selectable projects). This branch used to emit
    # profile.experiences / profile.projects wholesale, which re-admitted every gated slug
    # (fitness-tracker, spark-food-waste, ml-marketplace, personal-website, bu-engineering-it)
    # through the one door the guardrails do not watch. Pack the SAME guardrailed lists the
    # other strategies use, so there is no configuration in which a gated slug can reach a plan.
    if not candidates:
        if not experiences and not projects:
            raise OptimizerError(
                f"No selectable entries remain for role {role_name!r} after the selection guardrails "
                f"(profile has {len(profile.experiences)} experience(s) and {len(profile.projects)} "
                "project(s)). Refusing to emit a plan that ignores the guardrails; "
                "write the plan by hand and pass it with --plan."
            )
        exp_p, proj_p, lines = solve_line_budget_knapsack(experiences, projects, max_lines=MAX_EXPERIENCE_PROJECT_LINES)
        candidates.append({"experiences": exp_p, "projects": proj_p, "skills": "all", "_lines": lines})

    # De-duplicate: strategies can converge on the identical plan (e.g. strategy 1 at 35 lines and
    # strategy 3 at 32 lines both pack the same content when it fits under the tighter budget).
    # Keep the first (larger-budget) occurrence so the report doesn't score and list the same
    # configuration twice under two different "candidates tested" rows.
    unique: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for cand in candidates:
        key = json.dumps({k: v for k, v in cand.items() if not k.startswith("_")}, sort_keys=True)
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(cand)
    return unique


def optimize_plan(
    profile: Profile,
    jd_text: str,
    role_name: str = "software_engineer",
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Knapsack optimization search finding the highest-scoring plan within 1-page line budget.

    Every returned plan has been scored and compared. If no candidate could be scored the
    search has no winner, so this raises OptimizerError rather than handing back an
    arbitrary unranked candidate -- `apply` without --plan turns this return value directly
    into a delivered resume.
    """
    agent = HackerRankHiringAgent(role_name=role_name, jd_text=jd_text)
    candidates = generate_candidate_plans(profile, jd_text, role_name=role_name)
    results: list[dict[str, Any]] = []
    failures: list[tuple[str, str]] = []

    best_plan: dict[str, Any] | None = None
    best_eval: dict[str, Any] | None = None
    best_score = -1.0

    for cand in candidates:
        try:
            cand_clean = {k: v for k, v in cand.items() if not k.startswith("_")}
            selection = parse_plan(json.dumps(cand_clean), profile)
            plain_text = selection_to_plain_text(selection, profile)

            hr_eval = agent.evaluate(plain_text, candidate_name=profile.contact.name)
            total_score = float(hr_eval.get("total_score", 0.0))
            max_possible = int(hr_eval.get("max_possible", 100))
            bonus = float(hr_eval.get("bonus_points", {}).get("total", 0.0))

            projs = list(cand_clean.get("projects", {}).keys())
            lines_used = cand.get("_lines", 35.0)
            summary = f"Knapsack Plan: Projects [{', '.join(projs)}] ({lines_used:.1f} lines budgeted)"

            cand_res = {
                "plan_dict": cand_clean,
                "total_score": total_score,
                "max_possible": max_possible,
                "scores": hr_eval.get("scores", {}),
                "bonus_points": bonus,
                "lines_used": lines_used,
                "summary": summary,
            }
            results.append(cand_res)

            if total_score > best_score:
                best_score = total_score
                best_plan = cand_clean
                best_eval = hr_eval
                best_eval["lines_used"] = lines_used
        except Exception as exc:
            # Recorded, then re-surfaced below (raise if total, warn if partial) -- never swallowed.
            failures.append((type(exc).__name__, str(exc)))

    if best_plan is None or best_eval is None:
        raise OptimizerError(
            f"Scored none of the {len(candidates)} candidate plan(s) for role {role_name!r}; "
            f"refusing to return an unranked plan. Failures: {_describe_failures(failures)}"
        )

    if failures:
        report = {
            "failed": len(failures),
            "total": len(candidates),
            "errors": _failure_counts(failures),
        }
        best_eval["candidate_failures"] = report
        print(
            f"WARN: optimizer scored only {len(results)} of {len(candidates)} candidate plan(s) for "
            f"role {role_name!r}; the search space shrank. Failures: {_describe_failures(failures)}",
            file=sys.stderr,
        )

    results.sort(key=lambda r: r["total_score"], reverse=True)
    return best_plan, best_eval, results


def _failure_counts(failures: list[tuple[str, str]]) -> dict[str, dict[str, Any]]:
    """Collapse candidate scoring failures to distinct error types, each with an example message."""
    counts = Counter(name for name, _ in failures)
    examples: dict[str, str] = {}
    for name, message in failures:
        examples.setdefault(name, message)
    return {name: {"count": count, "example": examples[name]} for name, count in counts.items()}


def _describe_failures(failures: list[tuple[str, str]]) -> str:
    if not failures:
        return "none recorded (no candidate plans were generated)"
    return "; ".join(f"{name} x{data['count']}: {data['example']}" for name, data in _failure_counts(failures).items())


def format_optimization_report(
    best_plan: dict[str, Any],
    best_eval: dict[str, Any],
    results: list[dict[str, Any]],
) -> str:
    """Format the line-budgeted HackerRank optimization report and optimal plan."""
    role_title = best_eval.get("role_title", "Software Engineer")
    total_score = best_eval.get("total_score", 0.0)
    max_possible = best_eval.get("max_possible", 110)
    lines_used = best_eval.get("lines_used", 35.0)

    lines = [
        "=" * 68,
        f"HACKERRANK KNAPSACK OPTIMIZER REPORT: {role_title.upper()}",
        "=" * 68,
        "Solved 1-page line knapsack across candidate configurations",
        f"Winning Plan Score: {total_score:.1f} / {max_possible} points",
        f"1-Page Line Budget:  {lines_used:.1f} / {MAX_EXPERIENCE_PROJECT_LINES:.0f} lines ({lines_used / MAX_EXPERIENCE_PROJECT_LINES * 100:.0f}% capacity)",
    ]

    # A shrunken search space changes what "winning" means, so it belongs above the results,
    # not in a footnote under them.
    failures = best_eval.get("candidate_failures")
    if failures:
        lines.append(
            f"WARNING: {failures['failed']} of {failures['total']} candidate plan(s) failed to score "
            "and were excluded from the search."
        )
        for name, data in failures.get("errors", {}).items():
            lines.append(f"         {name} x{data['count']}: {data['example']}")

    lines.append("-" * 68)
    lines.append("CANDIDATE CONFIGURATIONS TESTED:")

    for rank, res in enumerate(results, start=1):
        marker = "🏆 [WINNER]" if rank == 1 else f"  #{rank}       "
        lines.append(
            f"{marker} Score: {res['total_score']:>5.1f} / {res['max_possible']} pts | Lines: {res['lines_used']:.1f}/{MAX_EXPERIENCE_PROJECT_LINES:.0f}"
        )
        lines.append(f"          {res['summary']}")

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
    lines.append("OPTIMAL PLAN JSON SELECTION (SORTED RELEVANCE ORDER):")
    lines.append(json.dumps(best_plan, indent=2))
    lines.append("=" * 68)
    return "\n".join(lines)
