"""Deterministic resume evaluation and scoring engine inspired by hiring rubrics."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .gates import GateResult, check_resume_gates, run_resume_gates

if TYPE_CHECKING:
    from .profile import Profile
    from .selection import Selection

COMMON_TECH_TERMS = {
    # Languages
    "c++",
    "c++17",
    "c++20",
    "c",
    "python",
    "rust",
    "java",
    "typescript",
    "javascript",
    "go",
    "golang",
    "sql",
    "cython",
    # Systems & Concurrency
    "concurrency",
    "multithreading",
    "lock-free",
    "spsc",
    "ring buffer",
    "low-latency",
    "latency",
    "distributed systems",
    "distributed",
    "networking",
    "tcp",
    "udp",
    "sockets",
    "ipc",
    "shared memory",
    "memory management",
    "cache",
    "profiling",
    "benchmarking",
    "throughput",
    "kernel",
    # Infra & Data
    "linux",
    "docker",
    "kubernetes",
    "k8s",
    "aws",
    "gcp",
    "azure",
    "ci/cd",
    "git",
    "postgresql",
    "postgres",
    "sqlite",
    "redis",
    "kafka",
    "grpc",
    "rest",
    "graphql",
    "faiss",
    "vector database",
    "etl",
    "pipeline",
    # Algorithms & Quant / ML
    "algorithms",
    "data structures",
    "pnl",
    "order book",
    "trading",
    "quant",
    "risk",
    "simulation",
    "stochastic",
    "machine learning",
    "ml",
    "nlp",
    "llm",
    "deep learning",
}

METRIC_PATTERNS = (
    r"\$\d+(?:,\d+)*(?:\.\d+)?[KkMBb]?",  # Dollar values ($8K, $1.5M)
    r"\b\d+(?:\.\d+)?%",  # Percentages (99%, 75.5%)
    r"\b\d+(?:\.\d+)?\s*(?:[muµn]s|ms|seconds|sec)\b",  # Latency (20µs, 5ms, 100ns)
    r"\b\d+(?:\.\d+)?[KkMBb]?\s*(?:req|queries|qps|events|users|rows|ops)\b",  # Scale/throughput
    r"\b\d+(?:\.\d+)?x\b",  # Multipliers (10x, 2.5x)
)


@dataclass(frozen=True)
class EvaluationReport:
    candidate_name: str
    overall_score: int
    role_alignment_score: int  # max 40
    technical_depth_score: int  # max 30
    impact_metrics_score: int  # max 20
    gate_compliance_score: int  # max 10
    matched_keywords: tuple[str, ...]
    missing_keywords: tuple[str, ...]
    extracted_metrics: tuple[str, ...]
    strengths: tuple[str, ...]
    suggestions: tuple[str, ...]
    gate_diagnostics: tuple[str, ...]


def _extract_technical_keywords(text: str) -> set[str]:
    """Extract known technical terms and domain concepts from raw text."""
    lower = text.lower()
    found = set()
    for term in COMMON_TECH_TERMS:
        pattern = r"\b" + re.escape(term) + r"\b"
        if term in ("c++", "c++17", "c++20", "ci/cd"):
            pattern = re.escape(term)
        if re.search(pattern, lower):
            found.add(term)
    return found


def _extract_metrics(text: str) -> list[str]:
    """Extract quantified metrics from resume text."""
    metrics = []
    for pattern in METRIC_PATTERNS:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        for m in matches:
            if m not in metrics:
                metrics.append(m)
    return metrics


def selection_to_plain_text(selection: Selection, profile: Profile) -> str:
    """Build unformatted plain text directly from a Selection and Profile model."""
    chunks = [
        profile.contact.name,
        profile.contact.email,
        profile.contact.phone,
    ]
    # Education
    for edu in profile.education:
        chunks.append(f"{edu.degree} {edu.institution}")
        chunks.extend(edu.coursework)

    # Selected Experiences
    for pick in selection.experiences:
        if pick.id in profile.experiences:
            exp = profile.experiences[pick.id]
            chunks.append(f"{exp.role} {exp.org}")
            for b_slug in pick.bullets:
                if b_slug in exp.bullets:
                    chunks.append(exp.bullets[b_slug])

    # Selected Projects
    for pick in selection.projects:
        if pick.id in profile.projects:
            proj = profile.projects[pick.id]
            chunks.append(f"{proj.name} {proj.tech}")
            for b_slug in pick.bullets:
                if b_slug in proj.bullets:
                    chunks.append(proj.bullets[b_slug])

    # Selected Skills
    for group, skills in selection.skills.items():
        chunks.append(group)
        chunks.extend(skills)

    return "\n".join(chunks)


def evaluate_resume_text(
    resume_text: str,
    jd_text: str,
    candidate_name: str = "Simon Chen",
    pdf_path: Path | None = None,
    gate_results: tuple[GateResult, ...] | None = None,
) -> EvaluationReport:
    """Deterministically score resume text against a job description rubric.

    Pass gate_results when the caller has already run the gates, so the PDF text layer is
    extracted once per evaluation rather than once here and once in the caller.
    """
    jd_keywords = _extract_technical_keywords(jd_text)
    resume_keywords = _extract_technical_keywords(resume_text)

    matched = sorted(jd_keywords & resume_keywords)
    missing = sorted(jd_keywords - resume_keywords)

    # 1. Role Alignment (0 - 40 pts)
    if jd_keywords:
        match_ratio = len(matched) / len(jd_keywords)
        role_alignment_score = min(40, round(match_ratio * 40))
    else:
        role_alignment_score = 35

    # 2. Technical Depth & Complexity (0 - 30 pts)
    depth_terms = {
        "c++",
        "c++17",
        "cython",
        "rust",
        "concurrency",
        "lock-free",
        "spsc",
        "low-latency",
        "shared memory",
        "memory management",
        "profiling",
        "distributed systems",
        "kernel",
    }
    found_depth = resume_keywords & depth_terms
    depth_ratio = min(1.0, len(found_depth) / 5)
    technical_depth_score = round(depth_ratio * 30)

    # 3. Impact & Quantified Metrics (0 - 20 pts)
    metrics = _extract_metrics(resume_text)
    impact_metrics_score = min(20, len(metrics) * 3)

    # 4. Quality Gate Compliance (0 - 10 pts)
    gate_score = 10
    gate_diagnostics: list[str] = []
    if gate_results is not None or pdf_path is not None:
        if gate_results is None and pdf_path is not None and not pdf_path.is_file():
            gate_score = 0
            gate_diagnostics.append(f"PDF file not found: {pdf_path}")
        else:
            gates = (
                gate_results
                if gate_results is not None
                else check_resume_gates(pdf_path, candidate_name=candidate_name, require_contact=False)  # type: ignore[arg-type]
            )
            failed_gates = [g for g in gates if not g.passed]
            if failed_gates:
                gate_score = max(0, 10 - len(failed_gates) * 3)
                for g in failed_gates:
                    gate_diagnostics.extend(g.diagnostics)

    overall_score = role_alignment_score + technical_depth_score + impact_metrics_score + gate_score

    # Strengths & Suggestions
    strengths = []
    if role_alignment_score >= 32:
        strengths.append(f"Strong tech stack alignment ({len(matched)} matched keywords: {', '.join(matched[:5])})")
    if technical_depth_score >= 24:
        strengths.append("High engineering signal with low-level systems & concurrency experience")
    if impact_metrics_score >= 15:
        strengths.append(f"Rich quantified metrics across experience and projects ({len(metrics)} distinct metrics)")

    suggestions = []
    if missing:
        prominent_missing = missing[:4]
        suggestions.append(f"Consider highlighting JD competencies if applicable: {', '.join(prominent_missing)}")
    if impact_metrics_score < 12:
        suggestions.append("Add more quantified impact and performance numbers to bullet points")

    return EvaluationReport(
        candidate_name=candidate_name,
        overall_score=overall_score,
        role_alignment_score=role_alignment_score,
        technical_depth_score=technical_depth_score,
        impact_metrics_score=impact_metrics_score,
        gate_compliance_score=gate_score,
        matched_keywords=tuple(matched),
        missing_keywords=tuple(missing),
        extracted_metrics=tuple(metrics),
        strengths=tuple(strengths),
        suggestions=tuple(suggestions),
        gate_diagnostics=tuple(gate_diagnostics),
    )


def evaluate_pdf_against_jd(pdf_path: Path, jd_text: str, candidate_name: str = "Simon Chen") -> EvaluationReport:
    """Evaluate a compiled PDF file directly against a job description."""
    # Diagnostic scoring, not delivery: only a name is available here, so an unverifiable
    # email/phone must not be reported as a gate failure. apply() runs the strict form.
    gates, ats_res = run_resume_gates(pdf_path, candidate_name=candidate_name, require_contact=False)
    return evaluate_resume_text(
        resume_text=ats_res.text,
        jd_text=jd_text,
        candidate_name=candidate_name,
        pdf_path=pdf_path,
        gate_results=gates,
    )


def format_evaluation_report(report: EvaluationReport, target_role: str = "Target Role") -> str:
    """Render a human-readable diagnostic report for terminal display."""
    lines = [
        "=" * 64,
        f"RESUME EVALUATION REPORT: {target_role.upper()}",
        "=" * 64,
        f"Candidate:           {report.candidate_name}",
        f"Overall Match Score: {report.overall_score} / 100",
        "-" * 64,
        "SCORE BREAKDOWN:",
        f"  • Role Alignment:       {report.role_alignment_score:>2} / 40  ({len(report.matched_keywords)} matched tech terms)",
        f"  • Technical Depth:      {report.technical_depth_score:>2} / 30  (Architecture & systems density)",
        f"  • Impact & Evidence:    {report.impact_metrics_score:>2} / 20  ({len(report.extracted_metrics)} quantified metrics)",
        f"  • Gate Compliance:      {report.gate_compliance_score:>2} / 10  (Strict 1-page & ATS checks)",
        "-" * 64,
    ]

    if report.matched_keywords:
        lines.append(f"Matched Competencies: {', '.join(report.matched_keywords)}")
    if report.missing_keywords:
        lines.append(f"Missing from Resume:  {', '.join(report.missing_keywords[:6])}")
    if report.strengths:
        lines.append("\nKey Strengths:")
        for s in report.strengths:
            lines.append(f"  + {s}")
    if report.suggestions:
        lines.append("\nTuning Suggestions:")
        for sug in report.suggestions:
            lines.append(f"  - {sug}")
    if report.gate_diagnostics:
        lines.append("\nGate Warnings:")
        for warn in report.gate_diagnostics:
            lines.append(f"  ! {warn}")

    lines.append("=" * 64)
    return "\n".join(lines)
