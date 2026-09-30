"""Integration tests for the worksisyphus ingest CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from worksisyphus.adapters.inbound.cli.commands import main
from worksisyphus.adapters.outbound.ingestion.scratch_bridge import ScratchBridge
from worksisyphus.core.domain.ingestion import RawJobPayload


def test_cli_ingest_no_args_fails() -> None:
    with pytest.raises(SystemExit):
        main(["ingest"])


def test_cli_ingest_fetch_and_clean_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bridge = ScratchBridge(scratch_dir=tmp_path)
    mock_payload = RawJobPayload(
        url="https://stripe.com/jobs/123",
        raw_content="<html><body><script>track();</script><h1>Backend Engineer</h1><p>We build payments.</p></body></html>",
        content_type="text/html",
        source_hint="web",
        fetched_at="2026-09-23T20:00:00Z",
    )

    with (
        patch(
            "worksisyphus.adapters.inbound.cli.handlers.ingest.ScratchBridge",
            return_value=bridge,
        ),
        patch(
            "worksisyphus.adapters.inbound.cli.handlers.ingest.HttpRawFetcher.fetch",
            return_value=mock_payload,
        ),
    ):
        code = main(["ingest", "https://stripe.com/jobs/123"])
        assert code == 0
        out = capsys.readouterr().out
        assert "Ingested:  https://stripe.com/jobs/123" in out
        assert "Saved:" in out

        scratch_jd = bridge.read_current_jd()
        assert "track();" not in scratch_jd
        assert "Backend Engineer" in scratch_jd
        assert "We build payments." in scratch_jd


def test_cli_ingest_custom_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_file = tmp_path / "custom_jd.txt"
    mock_payload = RawJobPayload(
        url="https://example.com/job",
        raw_content="<p>Custom JD content.</p>",
        content_type="text/html",
        source_hint="web",
        fetched_at="2026-09-23T20:00:00Z",
    )

    with patch(
        "worksisyphus.adapters.inbound.cli.handlers.ingest.HttpRawFetcher.fetch",
        return_value=mock_payload,
    ):
        code = main(["ingest", "https://example.com/job", "--output", str(out_file)])
        assert code == 0
        assert out_file.is_file()
        assert "Custom JD content." in out_file.read_text(encoding="utf-8")
