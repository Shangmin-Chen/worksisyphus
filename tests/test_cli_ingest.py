"""Integration tests for the worksisyphus ingest CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from worksisyphus.adapters.inbound.cli.commands import main
from worksisyphus.adapters.outbound.ingestion.scratch_bridge import ScratchBridge
from worksisyphus.core.domain.ingestion import RawJobPayload

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "postings"


def test_cli_ingest_no_args_fails(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["ingest"])
    assert code == 1
    err = capsys.readouterr().err
    assert "error: Ingestion target required" in err


def test_cli_ingest_fetch_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bridge = ScratchBridge(scratch_dir=tmp_path)
    output_file = tmp_path / "fetched_jd.txt"

    mock_payload = RawJobPayload(
        url="https://boards.greenhouse.io/stripe/jobs/123",
        raw_content="<h1>Software Engineer</h1><p>We are building global payment infrastructure.</p>",
        content_type="text/html",
        source_hint="generic",
        fetched_at="2026-09-23T20:00:00Z",
    )

    with (
        patch("worksisyphus.adapters.inbound.cli.handlers.ingest.ScratchBridge", return_value=bridge),
        patch("worksisyphus.adapters.inbound.cli.handlers.ingest.HttpRawFetcher.fetch", return_value=mock_payload),
    ):
        code = main(["ingest", "fetch", "https://boards.greenhouse.io/stripe/jobs/123", "--output", str(output_file)])
        assert code == 0
        assert output_file.is_file()
        assert "global payment infrastructure" in output_file.read_text(encoding="utf-8")
        out = capsys.readouterr().out
        assert "Fetched and pre-cleaned JD" in out


def test_cli_ingest_compile_from_fixture_file(capsys: pytest.CaptureFixture[str]) -> None:
    fixture_path = FIXTURES_DIR / "greenhouse_stripe.json"
    code = main(
        [
            "ingest",
            "compile",
            "--file",
            str(fixture_path),
            "--company",
            "Stripe",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Company:   Stripe" in out
    assert "Staff Software Engineer, Global Infrastructure" in out
    assert "Questions: 3 screening questions extracted" in out


def test_cli_ingest_compile_json_flag(capsys: pytest.CaptureFixture[str]) -> None:
    fixture_path = FIXTURES_DIR / "ashby_linear.json"
    code = main(
        [
            "ingest",
            "compile",
            "--file",
            str(fixture_path),
            "--json",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["company"] == "Linear"
    assert parsed["role"] == "Product Engineer, Backend Systems"
    assert parsed["jd_word_count"] > 10


def test_cli_ingest_oneshot_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bridge = ScratchBridge(scratch_dir=tmp_path)
    fixture_path = FIXTURES_DIR / "lever_palantir.json"
    lever_json = fixture_path.read_text(encoding="utf-8")

    mock_payload = RawJobPayload(
        url="https://jobs.lever.co/palantir/575e0037-1234-4567-89ab-cdef01234567",
        raw_content=lever_json,
        content_type="application/json",
        source_hint="lever",
        fetched_at="2026-09-23T20:00:00Z",
    )

    with (
        patch("worksisyphus.adapters.inbound.cli.handlers.ingest.ScratchBridge", return_value=bridge),
        patch("worksisyphus.adapters.inbound.cli.handlers.ingest.HttpRawFetcher.fetch", return_value=mock_payload),
    ):
        code = main(["ingest", "https://jobs.lever.co/palantir/575e0037-1234-4567-89ab-cdef01234567"])
        assert code == 0
        out = capsys.readouterr().out
        assert "Company:   Palantir" in out
        assert "Forward Deployed Software Engineer" in out
        assert "Questions: 2 screening questions extracted" in out
        assert (tmp_path / "current_jd.txt").is_file()
