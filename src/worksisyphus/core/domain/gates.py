"""Core domain quality gate rules and invariants."""

from __future__ import annotations

import re
from typing import NamedTuple

from .models import Profile

BANNED_TOOLS = (
    "sonarr",
    "radarr",
    "prowlarr",
    "jellyfin",
    "qbittorrent",
    "slskd",
    "soulseek",
)

BANNED_METRIC_PATTERNS = (
    r"uptime by 15%",
    r"100% incident resolution",
)

GPA_PATTERNS = (
    r"\bgpa\b",
    r"\bgpa\s*[:._-]+\s*\d\.\d{1,3}\b",
    r"\bgpa(?![:._-])(?!2\.0\b)\d\.\d{1,3}\b",
    r"\bgpa2\.0",
    r"\bgpa[34](?!\d)\b",
    r"\bcgpa\b",
    r"\bcgpa\s*[:._-]+\s*\d\.\d{1,3}\b",
    r"\bcgpa(?![:._-])(?!2\.0\b)\d\.\d{1,3}\b",
    r"\bcgpa2\.0",
    r"\bcgpa[34](?!\d)\b",
    r"\bg[.,/\-_\s]+p[.,/\-_\s]*a(?!\d{2,})(?:\b|\.?\d)",
    r"\bc[.,/\-_\s]+g[.,/\-_\s]+p[.,/\-_\s]*a(?!\d{2,})(?:\b|\.?\d)",
    r"grade[\s\-]+point[\s\-]+average",
    r"\b[234]\.\d{1,2}\s*/\s*4(?:\.0)?\b",
)

LATEX_LEAK_PATTERNS = (
    r"\\textbf\{",
    r"\\resumeItem\{",
    r"\\resumeSubheading",
    r"\\resumeProjectHeading",
    r"\\resumeItemListStart",
    r"\\resumeItemListEnd",
    r"\\vspace\{",
    r"\\emph\{",
)


MIN_WORDS_TAILORED = 350
MIN_WORDS_COMPILED = 900
MIN_CHARS_TAILORED = 1500
MIN_CHARS_COMPILED = 4000


class GateResult(NamedTuple):
    """Result of evaluating a specific quality gate."""

    gate_name: str
    passed: bool
    diagnostics: tuple[str, ...] = ()


def check_gpa_gate(text: str) -> GateResult:
    """Ensure no GPA metrics appear on the resume (Simon's policy)."""
    violations = []
    for pattern in GPA_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            matched_str = match.group(0)
            if "/" in matched_str:
                start, end = match.start(), match.end()
                prefix = text[max(0, start - 15) : start].lower()
                suffix = text[end : min(len(text), end + 25)].lower()
                if any(w in prefix for w in ("python", "version", "v.", "kernel")) or any(
                    suffix.strip().startswith(unit)
                    for unit in (
                        "worker",
                        "process",
                        "thread",
                        "node",
                        "core",
                        "cpu",
                        "gpu",
                        "instance",
                        "replica",
                        "shard",
                        "task",
                        "slot",
                        "stage",
                        "partition",
                        "server",
                        "service",
                        "pod",
                        "container",
                        "hour",
                        "month",
                        "day",
                        "week",
                        "year",
                    )
                ):
                    continue
            violations.append(f"Found GPA reference matching {pattern!r}: {[matched_str]}")
    return GateResult(
        gate_name="No-GPA Gate",
        passed=len(violations) == 0,
        diagnostics=tuple(violations),
    )


def check_banned_content_gate(text: str) -> GateResult:
    """Ensure no piracy-adjacent tools or fake-sounding metrics appear."""
    violations = []
    lower = text.lower()
    for tool in BANNED_TOOLS:
        if re.search(rf"\b{re.escape(tool)}\b", lower):
            violations.append(f"Found banned tooling name: {tool!r}")
    for pattern in BANNED_METRIC_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            violations.append(f"Found banned metric pattern: {pattern!r}")
    return GateResult(
        gate_name="Banned Content Gate",
        passed=len(violations) == 0,
        diagnostics=tuple(violations),
    )


def check_latex_leak_gate(text: str) -> GateResult:
    """Ensure raw LaTeX control sequences do not leak into the extracted text layer."""
    violations = []
    for pattern in LATEX_LEAK_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            violations.append(f"Found unrendered LaTeX code in PDF text: {matches}")
    return GateResult(
        gate_name="LaTeX Code Leak Gate",
        passed=len(violations) == 0,
        diagnostics=tuple(violations),
    )


def check_density_gate(text: str, is_tailored: bool = True) -> GateResult:
    """Crude length check ensuring baseline word and character counts; not a quality score.

    Ensures the extracted text layer meets minimum length thresholds so that an empty
    or severely truncated PDF fails delivery. Note: this is a crude token/character count,
    not a semantic quality assessment.
    """
    words = len(text.split())
    chars = len(text.strip())
    min_words = 350 if is_tailored else 900
    min_chars = 1500 if is_tailored else 4000

    violations = []
    if words < min_words:
        violations.append(f"Word count too low: {words} words (expected >= {min_words})")
    if chars < min_chars:
        violations.append(f"Character count too low: {chars} chars (expected >= {min_chars})")

    return GateResult(
        gate_name="Content Density Gate",
        passed=len(violations) == 0,
        diagnostics=tuple(violations),
    )


def profile_to_plain_text(profile: Profile) -> str:
    """Extract all text tokens and strings from a Profile for policy scanning."""
    chunks: list[str] = []
    if profile.contact:
        chunks.extend(
            [
                profile.contact.name,
                profile.contact.email,
                profile.contact.phone,
                profile.contact.website,
                profile.contact.github,
                profile.contact.linkedin,
            ]
        )
    for edu in profile.education:
        chunks.extend([edu.institution, edu.degree, edu.location, edu.date, *edu.coursework])
    for exp in profile.experiences.values():
        chunks.extend([exp.org, exp.role, exp.location, exp.date, *exp.bullets.values()])
    for proj in profile.projects.values():
        chunks.extend([proj.name, proj.tech, proj.date, *proj.bullets.values()])
    for group, skills in profile.skills.items():
        chunks.append(group)
        chunks.extend(skills)
    return "\n".join(filter(None, chunks))


def check_profile_gates(profile: Profile, *, allow_gpa: bool = False) -> tuple[GateResult, ...]:
    """Scan Profile content for No-GPA and Banned Content policy violations."""
    text = profile_to_plain_text(profile)
    gpa_gate = (
        GateResult(gate_name="No-GPA Gate", passed=True, diagnostics=("Allowed by compiler config",))
        if allow_gpa
        else check_gpa_gate(text)
    )
    return (
        gpa_gate,
        check_banned_content_gate(text),
    )
