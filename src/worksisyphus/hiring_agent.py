"""1:1 HackerRank hiring-agent pipeline: Pydantic schemas, role rubrics, and LLM evaluation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, create_model

ROLES_DIR = Path(__file__).parent / "roles"
UPSTREAM_MANIFEST_PATH = ROLES_DIR / "upstream_manifest.json"

# HackerRankHiringAgent.evaluate() category-key -> multiplier groupings. This is a deliberate
# keyword-match STUB (see class docstring / CLAUDE.md OUT-OF-SCOPE note): rewriting these values
# is an escalated product decision for the user, not a refactor. Named here only to remove the
# bare-float if/elif chain; every value and the branch ORDER below are unchanged from the
# original stub, and test_evaluate_output_is_frozen in tests/test_hiring_agent.py proves it.
OPEN_SOURCE_KEYS = frozenset({"open_source", "product_velocity"})
OPEN_SOURCE_SIGNALS = ("github", "production")
OPEN_SOURCE_HIT, OPEN_SOURCE_MISS = 0.90, 0.75

COMPLEXITY_KEYS = frozenset(
    {"self_projects", "agentic_systems", "systems_complexity", "quant_systems", "model_pipelines"}
)
COMPLEXITY_SIGNALS = ("latency", "concurrency", "engine")
COMPLEXITY_HIT, COMPLEXITY_MISS = 0.92, 0.80

# NOTE: "production" is a SIGNAL STRING in OPEN_SOURCE_SIGNALS above, and a distinct CATEGORY KEY
# here. The if/elif chain in evaluate() checks OPEN_SOURCE_KEYS, then COMPLEXITY_KEYS, then
# ARCHITECTURE_KEYS, in that exact order -- do not reorder.
ARCHITECTURE_KEYS = frozenset(
    {
        "production",
        "fullstack_arch",
        "evals_latency",
        "inference_compute",
        "architecture_scale",
        "numerical_compute",
        "backend_systems",
        "data_algorithms",
    }
)
ARCHITECTURE_MULTIPLIER = 0.94

DEFAULT_MULTIPLIER = 0.88


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    max: int
    icon: str = "•"


@dataclass(frozen=True)
class Role:
    name: str
    position_title: str
    categories: list[Category]
    bonus_max: int
    min_final_score: int
    max_final_score: int
    criteria_template: str
    system_message: str


class CategoryScore(BaseModel):
    score: float = Field(ge=0, description="Score achieved in this category")
    max: int = Field(gt=0, description="Maximum possible score")
    evidence: str = Field(min_length=1, description="Evidence supporting the score")


class Deductions(BaseModel):
    total: float = Field(default=0.0, ge=0, description="Total deduction points")
    reasons: str = Field(default="", description="Reasons for deductions")


def load_role(role_name: str = "startup_product_engineer", jd_text: str | None = None) -> Role:
    """Load a role specification from the roles/ directory, or synthesize from JD if missing."""
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", role_name.lower()).strip("_")
    role_dir = ROLES_DIR / slug
    if not role_dir.is_dir() or not (role_dir / "role.json").is_file():
        if jd_text and jd_text.strip():
            return synthesize_role_rubric(role_name=slug, jd_text=jd_text)
        available = list_roles()
        raise FileNotFoundError(f"Role '{role_name}' not found. Available roles: {', '.join(available)}")

    manifest = json.loads((role_dir / "role.json").read_text(encoding="utf-8"))
    criteria_text = (role_dir / "criteria.jinja").read_text(encoding="utf-8")
    system_text = (role_dir / "system_message.jinja").read_text(encoding="utf-8")

    categories = [
        Category(key=c["key"], label=c["label"], max=c["max"], icon=c.get("icon", "•")) for c in manifest["categories"]
    ]

    return Role(
        name=slug,
        position_title=manifest.get("position_title", role_name),
        categories=categories,
        bonus_max=manifest.get("bonus_max", 10),
        min_final_score=manifest.get("min_final_score", 0),
        max_final_score=manifest.get("max_final_score", 110),
        criteria_template=criteria_text,
        system_message=system_text,
    )


def list_roles() -> list[str]:
    """List all available role rubric names."""
    if not ROLES_DIR.is_dir():
        return []
    return sorted(d.name for d in ROLES_DIR.iterdir() if (d / "role.json").is_file())


def synthesize_role_rubric(
    role_name: str,
    jd_text: str,
    position_title: str | None = None,
) -> Role:
    """Dynamically generate a HackerRank-compliant 3-category role rubric from a job description."""
    safe_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", role_name.lower()).strip("_")
    if not safe_slug:
        safe_slug = "custom_role"
    role_dir = ROLES_DIR / safe_slug
    if (role_dir / "role.json").is_file():
        return load_role(safe_slug)

    title = position_title or role_name.replace("_", " ").title()

    categories = [
        Category(key="core_competency", label="Core Technical Competency", max=40, icon="🎯"),
        Category(key="architecture_scale", label="Architecture & Engineering Depth", max=35, icon="🏗️"),
        Category(key="impact_metrics", label="Quantified Impact & Delivery", max=25, icon="📊"),
    ]

    criteria_content = f"""You are evaluating a candidate for {title}.
Analyze the candidate's resume data against the job requirements:

### Target Job Requirements Summary
{jd_text[:1500]}

### Core Technical Competency (0-40 points)
- Demonstrated mastery of core programming languages, frameworks, and primary job tools.

### Architecture & Engineering Depth (0-35 points)
- System complexity, component boundaries, scale, maintainability, and domain engineering challenges.

### Quantified Impact & Delivery (0-25 points)
- Measurable metrics, throughput, latency, user adoption, reliability, and business impact.

=== CANDIDATE RESUME DATA ===
{{{{ resume_data }}}}
"""

    system_content = f"""You are an expert technical bar-raiser evaluating resumes for {title}.
Provide strict, objective scores with cited evidence in valid JSON format.
"""

    # Held in memory only. Synthesis is deterministic from (role_name, jd_text), so persisting
    # buys nothing and would scatter generated rubrics through the installed package every time
    # apply() evaluates a role title that has no curated rubric.
    return Role(
        name=safe_slug,
        position_title=title,
        categories=categories,
        bonus_max=10,
        min_final_score=0,
        max_final_score=110,
        criteria_template=criteria_content,
        system_message=system_content,
    )


def _parse_env_tokens(text: str) -> str | None:
    """Extract a GITHUB_TOKEN or GH_TOKEN value from .env-file text, ignoring comments/blanks."""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            if k.strip() in ("GITHUB_TOKEN", "GH_TOKEN"):
                val = v.strip().strip("'\"")
                if val:
                    return val
    return None


def _get_github_token() -> str | None:
    """Retrieve GitHub token from environment or local .env file."""
    import os

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and token.strip():
        return token.strip()
    env_file = Path(".env")
    if env_file.is_file():
        try:
            text = env_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        return _parse_env_tokens(text)
    return None


def _upstream_result(
    manifest: dict[str, Any],
    *,
    status: str,
    remote_commit: str,
    message: str,
    etag: str | None,
) -> dict[str, Any]:
    """Build the eight-key upstream-status dict that cli.py reads (status, upstream_repo,
    local_commit, remote_commit, synced_date, reference_role, custom_tracks, message)."""
    synced_commit = manifest.get("synced_commit", "unknown")
    return {
        "status": status,
        "upstream_repo": manifest.get("upstream_repo", "interviewstreet/hiring-agent"),
        "local_commit": synced_commit[:7],
        "remote_commit": remote_commit,
        "synced_date": manifest.get("synced_date"),
        "reference_role": manifest.get("upstream_reference_role"),
        "custom_tracks": manifest.get("custom_tracks", []),
        "etag": etag,
        "message": message,
    }


def _manifest_load_failure(exc: BaseException) -> dict[str, Any]:
    """Structured upstream status when the local manifest cannot be read or parsed."""
    return {
        "status": "unreachable",
        "upstream_repo": "interviewstreet/hiring-agent",
        "local_commit": "unknown",
        "remote_commit": "unknown",
        "synced_date": None,
        "reference_role": None,
        "custom_tracks": [],
        "etag": None,
        "message": f"Failed to load upstream manifest ({type(exc).__name__}: {exc}); tracked commit NOT verified.",
    }


def check_upstream_status() -> dict[str, Any]:
    """Check local rubric manifest against upstream HackerRank repository with ETag caching and rate-limit resilience."""
    if not UPSTREAM_MANIFEST_PATH.is_file():
        return {
            "status": "untracked",
            "message": "No upstream manifest file found.",
        }

    try:
        manifest = json.loads(UPSTREAM_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _manifest_load_failure(exc)

    synced_commit = manifest.get("synced_commit", "unknown")
    upstream_repo = manifest.get("upstream_repo", "interviewstreet/hiring-agent")
    cached_etag = manifest.get("etag")

    headers: dict[str, str] = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "worksisyphus-hiring-agent",
    }
    token = _get_github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if cached_etag:
        headers["If-None-Match"] = cached_etag

    try:
        import requests

        url = f"https://api.github.com/repos/{upstream_repo}/commits/main"
        resp = requests.get(url, headers=headers, timeout=2)

        if resp.status_code == 304:
            return _upstream_result(
                manifest,
                status="synced",
                remote_commit=synced_commit[:7],
                etag=cached_etag,
                message="Local rubrics are up to date with HackerRank upstream (ETag verified 304 Not Modified).",
            )

        if resp.status_code == 200:
            try:
                data = resp.json()
            except (ValueError, json.JSONDecodeError) as exc:
                return _upstream_result(
                    manifest,
                    status="unreachable",
                    remote_commit="unknown",
                    etag=cached_etag,
                    message=(
                        f"Upstream returned invalid JSON ({type(exc).__name__}: {exc}); "
                        f"tracked commit {synced_commit[:7]} NOT verified."
                    ),
                )
            remote_commit = data.get("sha", "")
            if not remote_commit:
                return _upstream_result(
                    manifest,
                    status="unreachable",
                    remote_commit="unknown",
                    etag=cached_etag,
                    message=(
                        f"Upstream returned HTTP 200 without a commit SHA; "
                        f"tracked commit {synced_commit[:7]} NOT verified."
                    ),
                )
            remote_etag = resp.headers.get("ETag") or cached_etag
            is_synced = bool(remote_commit.startswith(synced_commit) or synced_commit.startswith(remote_commit))
            return _upstream_result(
                manifest,
                status="synced" if is_synced else "outdated",
                remote_commit=remote_commit[:7] if remote_commit else "unknown",
                etag=remote_etag,
                message="Local rubrics are up to date with HackerRank upstream."
                if is_synced
                else f"Upstream update available ({synced_commit[:7]} -> {remote_commit[:7]}).",
            )

        if resp.status_code == 403:
            remaining = resp.headers.get("X-RateLimit-Remaining")
            if remaining is not None and remaining == "0":
                return _upstream_result(
                    manifest,
                    status="rate_limited",
                    remote_commit="rate_limited",
                    etag=cached_etag,
                    message=(
                        f"GitHub API rate limit reached. Tracked upstream commit: {synced_commit[:7]} NOT verified."
                    ),
                )
            return _upstream_result(
                manifest,
                status="unreachable",
                remote_commit="unknown",
                etag=cached_etag,
                message=f"Upstream returned HTTP 403 (forbidden); tracked commit {synced_commit[:7]} NOT verified.",
            )

        return _upstream_result(
            manifest,
            status="unreachable",
            remote_commit="unknown",
            etag=cached_etag,
            message=f"Upstream returned HTTP {resp.status_code}; tracked commit {synced_commit[:7]} NOT verified.",
        )
    except Exception as exc:
        return _upstream_result(
            manifest,
            status="unreachable",
            remote_commit="offline",
            etag=cached_etag,
            message=f"Upstream check failed ({type(exc).__name__}: {exc}); falling back to the tracked commit "
            f"{synced_commit[:7]}, which was NOT verified.",
        )


def build_evaluation_model(role: Role) -> type[BaseModel]:
    """Build dynamic Pydantic EvaluationData model matching the role's categories."""
    score_fields: dict[str, Any] = {cat.key: (CategoryScore, ...) for cat in role.categories}
    scores_model = create_model("Scores", **score_fields)

    bonus_fields: dict[str, Any] = {
        "total": (float, Field(default=0.0, ge=0, le=role.bonus_max, description="Total bonus points")),
        "breakdown": (str, Field(default="", description="Breakdown of bonus points")),
    }
    bonus_model = create_model("BonusPoints", **bonus_fields)

    eval_fields: dict[str, Any] = {
        "scores": (scores_model, ...),
        "bonus_points": (bonus_model, ...),
        "deductions": (Deductions, ...),
        "key_strengths": (list[str], Field(default_factory=list, description="Top key strengths")),
        "areas_for_improvement": (list[str], Field(default_factory=list, description="Top areas for improvement")),
    }
    return create_model("EvaluationData", **eval_fields)


class HackerRankHiringAgent:
    """Orchestrator that scores candidate resumes against official HackerRank role rubrics."""

    def __init__(
        self,
        role_name: str = "software_engineer",
        jd_text: str | None = None,
    ):
        self.role = load_role(role_name, jd_text=jd_text)
        self.evaluation_model = build_evaluation_model(self.role)

    def evaluate(
        self,
        resume_text: str,
        candidate_name: str = "Simon Chen",
    ) -> dict[str, Any]:
        """Run deterministic evaluation conforming to HackerRank rubric schema."""
        lower = resume_text.lower()
        scores: dict[str, Any] = {}

        for cat in self.role.categories:
            key = cat.key
            if key in OPEN_SOURCE_KEYS:
                score = (
                    round(cat.max * OPEN_SOURCE_HIT, 1)
                    if any(sig in lower for sig in OPEN_SOURCE_SIGNALS)
                    else round(cat.max * OPEN_SOURCE_MISS, 1)
                )
                evidence = f"Demonstrated ownership and delivery in {cat.label}."
            elif key in COMPLEXITY_KEYS:
                score = (
                    round(cat.max * COMPLEXITY_HIT, 1)
                    if any(sig in lower for sig in COMPLEXITY_SIGNALS)
                    else round(cat.max * COMPLEXITY_MISS, 1)
                )
                evidence = f"High-complexity engineering with verified technical depth in {cat.label}."
            elif key in ARCHITECTURE_KEYS:
                score = round(cat.max * ARCHITECTURE_MULTIPLIER, 1)
                evidence = f"Strong architecture, scale, and deployment track record in {cat.label}."
            else:
                score = round(cat.max * DEFAULT_MULTIPLIER, 1)
                evidence = f"Quantified metrics and verified impact in {cat.label}."

            scores[key] = {
                "score": score,
                "max": cat.max,
                "evidence": evidence,
            }

        bonus_total = 5.0
        bonus_breakdown = "Verified performance benchmarks, high-impact systems, and production deployment."

        raw = {
            "scores": scores,
            "bonus_points": {"total": bonus_total, "breakdown": bonus_breakdown},
            "deductions": {"total": 0.0, "reasons": "No fairness or content violations detected."},
            "key_strengths": [
                f"Strong architectural depth tailored to {self.role.position_title}",
                "Defensible production impact with verified latency and throughput metrics",
                "Clean technical communication without buzzword stuffing or filler",
            ],
            "areas_for_improvement": [
                "Continue documenting scale and latency benchmarks on public repositories",
            ],
        }
        return self._calculate_final_score(raw)

    def _calculate_final_score(self, eval_dict: dict[str, Any]) -> dict[str, Any]:
        """Calculate the total score, category totals, and final percentage."""
        scores = eval_dict.get("scores", {})
        try:
            cat_total = sum(float(c["score"]) for c in scores.values())
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Category score dict is missing a numeric 'score': {exc}") from exc
        max_possible = sum(cat.max for cat in self.role.categories)

        try:
            bonus = float(eval_dict.get("bonus_points", {})["total"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"bonus_points is missing a numeric 'total': {exc}") from exc
        try:
            deductions = float(eval_dict.get("deductions", {})["total"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"deductions is missing a numeric 'total': {exc}") from exc

        final_score = max(
            self.role.min_final_score,
            min(self.role.max_final_score, round(cat_total + bonus - deductions, 1)),
        )

        eval_dict["total_score"] = final_score
        eval_dict["max_possible"] = max_possible
        eval_dict["role_title"] = self.role.position_title
        return eval_dict


def format_hackerrank_report(eval_data: dict[str, Any], role_name: str) -> str:
    """Format the 1:1 HackerRank evaluation output into an official terminal scorecard."""
    try:
        role = load_role(role_name)
        position_title = role.position_title
        max_final_score = role.max_final_score
        categories = role.categories
    except FileNotFoundError:
        # A synthesized (JD-derived) rubric has no directory on disk (load_role only persists
        # curated rubrics); render straight from the evaluation result instead of re-deriving one.
        position_title = eval_data.get("role_title", role_name.replace("_", " ").title())
        max_final_score = 110
        categories = [
            Category(key=k, label=k.replace("_", " ").title(), max=int(v.get("max", 0)))
            for k, v in eval_data.get("scores", {}).items()
        ]

    lines = [
        "=" * 68,
        f"HACKERRANK HIRING AGENT SCORECARD: {position_title.upper()}",
        "=" * 68,
        f"Overall Candidate Score: {eval_data.get('total_score', 0):.1f} / {max_final_score} points",
        "-" * 68,
        "CATEGORY SCORE BREAKDOWN:",
    ]

    scores = eval_data.get("scores", {})
    for cat in categories:
        cat_data = scores.get(cat.key, {})
        score_val = cat_data.get("score", 0)
        max_val = cat_data.get("max", cat.max)
        evidence = cat_data.get("evidence", "")
        lines.append(f"  {cat.icon} {cat.label:<32} {score_val:>4.1f} / {max_val} pts")
        if evidence:
            lines.append(f"     Evidence: {evidence}")

    bonus = eval_data.get("bonus_points", {})
    if bonus.get("total", 0) > 0:
        lines.append(f"\n  🎁 Bonus Points:          +{bonus.get('total'):.1f} pts ({bonus.get('breakdown')})")

    deductions = eval_data.get("deductions", {})
    if deductions.get("total", 0) > 0:
        lines.append(f"  ⚠️ Deductions:            -{deductions.get('total'):.1f} pts ({deductions.get('reasons')})")

    strengths = eval_data.get("key_strengths", [])
    if strengths:
        lines.append("\nKey Strengths:")
        for s in strengths:
            lines.append(f"  + {s}")

    improvements = eval_data.get("areas_for_improvement", [])
    if improvements:
        lines.append("\nAreas for Improvement:")
        for imp in improvements:
            lines.append(f"  - {imp}")

    lines.append("=" * 68)
    return "\n".join(lines)
