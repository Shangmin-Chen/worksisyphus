"""Deterministic ATS keyword extraction and matching engine.

Extracts technical keywords, n-grams, and concepts from job descriptions
and measures the resume's keyword coverage with synonym awareness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Canonical term -> aliases/synonyms
SYNONYM_MAP: dict[str, tuple[str, ...]] = {
    "c++": ("cpp", "cplusplus", "c++17", "c++20"),
    "c++17": ("c++", "cpp"),
    "c++20": ("c++", "cpp"),
    "python": ("python3", "py"),
    "golang": ("go",),
    "go": ("golang",),
    "kubernetes": ("k8s",),
    "k8s": ("kubernetes",),
    "postgresql": ("postgres", "psql"),
    "postgres": ("postgresql", "psql"),
    "node.js": ("nodejs", "node"),
    "nodejs": ("node.js", "node"),
    "react": ("react.js", "reactjs"),
    "react.js": ("react", "reactjs"),
    "next.js": ("nextjs", "next"),
    "nextjs": ("next.js", "next"),
    "ci/cd": ("cicd", "continuous integration"),
    "cicd": ("ci/cd", "continuous integration"),
    "low-latency": ("low latency",),
    "low latency": ("low-latency",),
    "lock-free": ("lockfree", "non-blocking"),
    "distributed systems": ("distributed",),
    "distributed": ("distributed systems",),
    "machine learning": ("ml",),
    "ml": ("machine learning",),
    "deep learning": ("neural networks",),
    "natural language processing": ("nlp",),
    "nlp": ("natural language processing",),
    "large language models": ("llm", "llms"),
    "llm": ("large language models", "llms"),
    "rest": ("restful", "rest api"),
    "restful": ("rest", "rest api"),
}

# Master list of recognized technical skills, languages, tools, and domain keywords
KNOWN_TECH_TERMS: tuple[str, ...] = (
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
    "bash",
    "shell",
    "zsh",
    "r",
    "ruby",
    "swift",
    "kotlin",
    "scala",
    "html",
    "css",
    # Systems & Architecture
    "concurrency",
    "multithreading",
    "lock-free",
    "spsc",
    "ring buffer",
    "low-latency",
    "low latency",
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
    "caching",
    "profiling",
    "benchmarking",
    "throughput",
    "kernel",
    "linux",
    "unix",
    "posix",
    "operating systems",
    "microservices",
    "streaming",
    "event-driven",
    # Infra, Cloud & DevOps
    "docker",
    "kubernetes",
    "k8s",
    "aws",
    "gcp",
    "azure",
    "ci/cd",
    "cicd",
    "git",
    "github actions",
    "terraform",
    "ansible",
    # Data, Storage & Messaging
    "postgresql",
    "postgres",
    "sqlite",
    "mysql",
    "redis",
    "kafka",
    "rabbitmq",
    "grpc",
    "rest",
    "restful",
    "graphql",
    "faiss",
    "vector database",
    "etl",
    "data pipeline",
    # Web & Frameworks
    "react",
    "react.js",
    "reactjs",
    "next.js",
    "nextjs",
    "node",
    "node.js",
    "nodejs",
    "express",
    "fastapi",
    "flask",
    "django",
    "vue",
    "angular",
    "svelte",
    "tailwind",
    # Quant, Algorithms & ML
    "algorithms",
    "data structures",
    "machine learning",
    "ml",
    "deep learning",
    "nlp",
    "llm",
    "pytorch",
    "tensorflow",
    "pandas",
    "numpy",
    "scikit-learn",
    "pnl",
    "order book",
    "trading",
    "quant",
    "quantitative",
    "risk",
    "simulation",
    "stochastic",
    "market data",
    # Roles & Domains
    "backend",
    "frontend",
    "full-stack",
    "fullstack",
    "systems",
    "infra",
    "infrastructure",
)


def _contains_term(text: str, term: str) -> bool:
    """Check if term appears in text as a complete token or phrase."""
    lower = text.lower()
    if term == "c":
        pattern = r"(?<![a-z0-9])c(?![a-z0-9+#])"
    elif any(ch in term for ch in ("+", "/", ".", "-")):
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
    else:
        pattern = rf"\b{re.escape(term)}\b"
    return bool(re.search(pattern, lower))


def extract_keywords(text: str) -> tuple[str, ...]:
    """Extract recognized technical keywords and phrases present in text."""
    if not text.strip():
        return ()
    found = []
    # Match multi-word terms first to avoid sub-word fragmentation
    sorted_terms = sorted(KNOWN_TECH_TERMS, key=lambda t: (-len(t), t))
    for term in sorted_terms:
        if _contains_term(text, term):
            found.append(term)
    return tuple(sorted(set(found)))


@dataclass(frozen=True)
class ATSKeywordMatchResult:
    """Result of deterministic ATS keyword matching between JD and resume."""

    coverage_score: float  # 0.0 to 100.0
    matched_keywords: tuple[str, ...]
    missing_keywords: tuple[str, ...]
    jd_keywords: tuple[str, ...]

    def as_meta(self) -> dict[str, Any]:
        return {
            "coverage_score": round(self.coverage_score, 1),
            "matched_keywords": list(self.matched_keywords),
            "missing_keywords": list(self.missing_keywords),
            "total_jd_keywords": len(self.jd_keywords),
            "matched_count": len(self.matched_keywords),
        }


def score_ats_keywords(resume_text: str, jd_text: str) -> ATSKeywordMatchResult:
    """Calculate keyword coverage of resume_text against jd_text with synonym expansion."""
    jd_keywords = extract_keywords(jd_text)
    if not jd_keywords:
        return ATSKeywordMatchResult(
            coverage_score=100.0,
            matched_keywords=(),
            missing_keywords=(),
            jd_keywords=(),
        )

    matched = []
    missing = []

    for kw in jd_keywords:
        # Check direct term match
        if _contains_term(resume_text, kw):
            matched.append(kw)
            continue

        # Check synonym / alias matches
        synonyms = SYNONYM_MAP.get(kw, ())
        if any(_contains_term(resume_text, syn) for syn in synonyms):
            matched.append(kw)
            continue

        missing.append(kw)

    coverage = (len(matched) / len(jd_keywords)) * 100.0
    return ATSKeywordMatchResult(
        coverage_score=round(coverage, 2),
        matched_keywords=tuple(sorted(matched)),
        missing_keywords=tuple(sorted(missing)),
        jd_keywords=jd_keywords,
    )
