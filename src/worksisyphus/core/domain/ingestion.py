"""Domain models and value objects for raw job ingestion and ETL posting compilation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScreeningQuestion:
    """A pre-screen or application question extracted from a job posting form."""

    question_id: str
    prompt: str
    question_type: str = "text"  # "text" | "textarea" | "select" | "boolean" | "file" | "generic"
    required: bool = False
    options: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("ScreeningQuestion prompt cannot be empty.")


@dataclass(frozen=True)
class RawJobPayload:
    """Unprocessed network payload and metadata returned by a fetcher."""

    url: str
    raw_content: str
    content_type: str  # "application/json" | "text/html"
    source_hint: str  # "greenhouse" | "lever" | "ashby" | "generic"
    fetched_at: str

    def __post_init__(self) -> None:
        if not self.url.strip():
            raise ValueError("RawJobPayload url cannot be empty.")
        if not self.raw_content:
            raise ValueError("RawJobPayload raw_content cannot be empty.")


@dataclass(frozen=True)
class JobPosting:
    """Normalized, validated job opportunity ready for downstream consumption."""

    company: str
    role: str
    jd_text: str
    url: str
    location: str = ""
    source_type: str = "generic"
    screening_questions: tuple[ScreeningQuestion, ...] = ()
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.company.strip():
            raise ValueError("JobPosting company cannot be empty.")
        if not self.role.strip():
            raise ValueError("JobPosting role cannot be empty.")
        if not self.jd_text.strip():
            raise ValueError("JobPosting jd_text cannot be empty.")
        if not self.url.strip():
            raise ValueError("JobPosting url cannot be empty.")
