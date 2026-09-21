"""Domain models and algorithms for candidate evaluation rubrics and scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Category:
    """Evaluation category within a role rubric."""

    key: str
    label: str
    max: int
    icon: str = "•"


@dataclass(frozen=True)
class Role:
    """Comprehensive rubric specification for evaluating resumes against a role."""

    name: str
    position_title: str
    categories: list[Category]
    bonus_max: int
    min_final_score: int
    max_final_score: int
    criteria_template: str
    system_message: str


class CategoryScore(BaseModel):
    """Score model for a single category."""

    score: float = Field(ge=0, description="Score achieved in this category")
    max: int = Field(gt=0, description="Maximum possible score")
    evidence: str = Field(min_length=1, description="Evidence supporting the score")


class Deductions(BaseModel):
    """Point deductions for formatting, missing info, or violations."""

    total: float = Field(default=0.0, ge=0, description="Total deduction points")
    reasons: str = Field(default="", description="Reasons for deductions")


def synthesize_role_rubric(
    role_name: str,
    jd_text: str,
    position_title: str | None = None,
) -> Role:
    """Dynamically generate a HackerRank-compliant 3-category role rubric from a job description."""
    safe_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", role_name.lower()).strip("_")
    if not safe_slug:
        safe_slug = "custom_role"

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
