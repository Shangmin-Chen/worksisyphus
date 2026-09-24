"""Unit tests for EtlJobTransformer using real-world fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from worksisyphus.adapters.outbound.ingestion.etl_compiler import EtlJobTransformer
from worksisyphus.core.domain.ingestion import RawJobPayload

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "postings"


def test_transform_greenhouse_fixture() -> None:
    fixture_path = FIXTURES_DIR / "greenhouse_stripe.json"
    raw_content = fixture_path.read_text(encoding="utf-8")
    payload = RawJobPayload(
        url="https://boards.greenhouse.io/stripe/jobs/5123456",
        raw_content=raw_content,
        content_type="application/json",
        source_hint="greenhouse",
        fetched_at="2026-09-23T20:00:00Z",
    )

    transformer = EtlJobTransformer()
    posting = transformer.transform(payload)

    assert posting.company == "Stripe"
    assert posting.role == "Staff Software Engineer, Global Infrastructure"
    assert posting.location == "Seattle, WA / Remote"
    assert "financial infrastructure platform" in posting.jd_text
    assert "Kafka and Raft" in posting.jd_text
    assert "Qualifications" in posting.jd_text

    # Screening questions
    assert len(posting.screening_questions) == 3
    q1 = posting.screening_questions[0]
    assert q1.question_id == "101"
    assert "employment sponsorship" in q1.prompt
    assert q1.question_type == "select"
    assert q1.required is True
    assert q1.options == ("No", "Yes")

    q2 = posting.screening_questions[1]
    assert q2.question_id == "102"
    assert q2.prompt == "LinkedIn Profile URL"
    assert q2.question_type == "text"
    assert q2.required is False

    q3 = posting.screening_questions[2]
    assert q3.question_id == "103"
    assert q3.question_type == "file"
    assert q3.required is True


def test_transform_lever_fixture() -> None:
    fixture_path = FIXTURES_DIR / "lever_palantir.json"
    raw_content = fixture_path.read_text(encoding="utf-8")
    payload = RawJobPayload(
        url="https://jobs.lever.co/palantir/575e0037-1234-4567-89ab-cdef01234567",
        raw_content=raw_content,
        content_type="application/json",
        source_hint="lever",
        fetched_at="2026-09-23T20:00:00Z",
    )

    transformer = EtlJobTransformer()
    posting = transformer.transform(payload)

    assert posting.company == "Palantir"
    assert posting.role == "Forward Deployed Software Engineer"
    assert posting.location == "New York, NY"
    assert "Palantir builds software" in posting.jd_text
    assert "What You Will Do:" in posting.jd_text
    assert "• Deploy production distributed pipelines" in posting.jd_text
    assert "What We Look For:" in posting.jd_text
    assert "• B.S. or higher in Computer Science" in posting.jd_text

    # Questions
    assert len(posting.screening_questions) == 2
    q1 = posting.screening_questions[0]
    assert q1.question_id == "clearance_status"
    assert "security clearance" in q1.prompt
    assert q1.question_type == "select"
    assert q1.required is True
    assert q1.options == ("None", "Secret", "Top Secret / SCI")


def test_transform_ashby_fixture() -> None:
    fixture_path = FIXTURES_DIR / "ashby_linear.json"
    raw_content = fixture_path.read_text(encoding="utf-8")
    payload = RawJobPayload(
        url="https://jobs.ashbyhq.com/linear/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        raw_content=raw_content,
        content_type="application/json",
        source_hint="ashby",
        fetched_at="2026-09-23T20:00:00Z",
    )

    transformer = EtlJobTransformer()
    posting = transformer.transform(payload)

    assert posting.company == "Linear"
    assert posting.role == "Product Engineer, Backend Systems"
    assert posting.location == "San Francisco, CA / Remote"
    assert "Linear is building the software" in posting.jd_text
    assert "WebSocket sync engine" in posting.jd_text


def test_transform_custom_html_fixture() -> None:
    fixture_path = FIXTURES_DIR / "custom_html_posting.html"
    raw_content = fixture_path.read_text(encoding="utf-8")
    payload = RawJobPayload(
        url="https://careers.datadoghq.com/jobs/123",
        raw_content=raw_content,
        content_type="text/html",
        source_hint="generic",
        fetched_at="2026-09-23T20:00:00Z",
    )

    transformer = EtlJobTransformer()
    posting = transformer.transform(payload)

    assert posting.company == "Datadog"
    assert posting.role == "Senior Systems Engineer, Core Platform"
    assert posting.location == "Boston, MA"
    assert "Datadog is the monitoring" in posting.jd_text
    assert "• Architect high-throughput ingest services" in posting.jd_text
    # Ensure noise was removed
    assert "About Us" not in posting.jd_text
    assert "All rights reserved." not in posting.jd_text


def test_transform_overrides_company_and_role() -> None:
    fixture_path = FIXTURES_DIR / "greenhouse_stripe.json"
    raw_content = fixture_path.read_text(encoding="utf-8")
    payload = RawJobPayload(
        url="https://boards.greenhouse.io/stripe/jobs/5123456",
        raw_content=raw_content,
        content_type="application/json",
        source_hint="greenhouse",
        fetched_at="2026-09-23T20:00:00Z",
    )

    transformer = EtlJobTransformer()
    posting = transformer.transform(
        payload,
        company_override="Stripe International",
        role_override="Principal Distributed Systems Architect",
    )

    assert posting.company == "Stripe International"
    assert posting.role == "Principal Distributed Systems Architect"


def test_transform_empty_content_raises() -> None:
    payload = RawJobPayload(
        url="https://example.com/job",
        raw_content="    ",
        content_type="text/html",
        source_hint="generic",
        fetched_at="2026-09-23T20:00:00Z",
    )
    transformer = EtlJobTransformer()
    with pytest.raises(ValueError, match="JobPosting jd_text cannot be empty"):
        transformer.transform(payload)
