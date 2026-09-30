"""Unit tests for ScratchBridge disk persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from worksisyphus.adapters.outbound.ingestion.scratch_bridge import ScratchBridge
from worksisyphus.core.domain.ingestion import RawJobPayload


def test_scratch_bridge_save_and_read_jd(tmp_path: Path) -> None:
    bridge = ScratchBridge(scratch_dir=tmp_path)
    sample_jd = "Senior Systems Engineer at Stripe\nRequirements:\n• 5+ years Go/Rust"

    saved_path = bridge.save_current_jd(sample_jd)
    assert saved_path.is_file()
    assert saved_path == tmp_path / "current_jd.txt"

    read_back = bridge.read_current_jd()
    assert read_back == sample_jd


def test_scratch_bridge_read_missing_file_raises(tmp_path: Path) -> None:
    bridge = ScratchBridge(scratch_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="Scratch JD file not found"):
        bridge.read_current_jd("non_existent.txt")


def test_scratch_bridge_save_and_load_payload(tmp_path: Path) -> None:
    bridge = ScratchBridge(scratch_dir=tmp_path)
    payload = RawJobPayload(
        url="https://boards.greenhouse.io/stripe/jobs/12345",
        raw_content='{"id": 12345, "title": "Staff Engineer"}',
        content_type="application/json",
        source_hint="greenhouse",
        fetched_at="2026-09-23T20:00:00Z",
    )

    saved_path = bridge.save_raw_payload(payload)
    assert saved_path.is_file()

    loaded = bridge.load_raw_payload()
    assert loaded.url == payload.url
    assert loaded.raw_content == payload.raw_content
    assert loaded.content_type == payload.content_type
    assert loaded.source_hint == payload.source_hint
    assert loaded.fetched_at == payload.fetched_at


def test_scratch_bridge_clear(tmp_path: Path) -> None:
    bridge = ScratchBridge(scratch_dir=tmp_path)
    bridge.save_current_jd("text 1", "file1.txt")
    bridge.save_current_jd("text 2", "file2.txt")
    assert len(list(tmp_path.glob("*"))) == 2

    bridge.clear()
    assert len(list(tmp_path.glob("*"))) == 0
