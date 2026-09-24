"""Unit and integration tests for Venue 1 (Track & Leads Vault)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from worksisyphus.adapters.inbound.cli.commands import main
from worksisyphus.adapters.outbound.ingestion.scratch_bridge import ScratchBridge
from worksisyphus.core.domain.ingestion import ScreeningQuestion
from worksisyphus.core.use_cases.tracker import (
    get_lead,
    list_leads,
    track_lead,
    update_lead_status,
)


def test_track_lead_creates_folder_and_files(tmp_path: Path) -> None:
    leads_dir = tmp_path / "leads"
    questions = (
        ScreeningQuestion(
            question_id="q1",
            prompt="Are you legally authorized to work in the US?",
            question_type="boolean",
            required=True,
        ),
    )

    lead_path = track_lead(
        company="Stripe",
        role="Infrastructure Engineer",
        jd_text="Stripe is hiring an infrastructure engineer.",
        url="https://stripe.com/jobs/123",
        questions=questions,
        leads_dir=leads_dir,
    )

    assert lead_path.is_dir()
    assert (lead_path / "meta.json").is_file()
    assert (lead_path / "jd.txt").is_file()
    assert (lead_path / "questions.json").is_file()

    meta = json.loads((lead_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["company"] == "Stripe"
    assert meta["role"] == "Infrastructure Engineer"
    assert meta["status"] == "tracked"
    assert meta["url"] == "https://stripe.com/jobs/123"

    assert (lead_path / "jd.txt").read_text(encoding="utf-8") == "Stripe is hiring an infrastructure engineer."

    q_data = json.loads((lead_path / "questions.json").read_text(encoding="utf-8"))
    assert len(q_data) == 1
    assert q_data[0]["id"] == "q1"


def test_track_lead_collision_allocation(tmp_path: Path) -> None:
    leads_dir = tmp_path / "leads"
    first = track_lead(
        company="Stripe",
        role="SWE",
        jd_text="JD text 1",
        leads_dir=leads_dir,
    )
    second = track_lead(
        company="Stripe",
        role="SWE",
        jd_text="JD text 2",
        leads_dir=leads_dir,
    )

    assert first != second
    assert second.name.endswith("_2")


def test_list_leads_and_get_lead(tmp_path: Path) -> None:
    leads_dir = tmp_path / "leads"
    track_lead(
        company="Palantir",
        role="Forward Deployed SWE",
        jd_text="Palantir JD",
        leads_dir=leads_dir,
    )

    leads = list_leads(leads_dir=leads_dir)
    assert len(leads) == 1
    assert leads[0]["company"] == "Palantir"

    folder, meta, jd = get_lead("palantir", leads_dir=leads_dir)
    assert folder.name == leads[0]["folder"]
    assert meta["company"] == "Palantir"
    assert jd == "Palantir JD"


def test_update_lead_status(tmp_path: Path) -> None:
    leads_dir = tmp_path / "leads"
    lead_path = track_lead(
        company="Linear",
        role="Product Engineer",
        jd_text="Linear JD",
        leads_dir=leads_dir,
    )

    update_lead_status("linear", "applied", leads_dir=leads_dir)
    meta = json.loads((lead_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "applied"


def test_cli_track_with_scratch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bridge = ScratchBridge(scratch_dir=tmp_path / "scratch")
    bridge.save_current_jd("Scratch JD text for Datadog")
    leads_dir = tmp_path / "leads"

    with (
        pytest.MonkeyPatch.context() as mp,
    ):
        mp.setattr(
            "worksisyphus.adapters.inbound.cli.handlers.track.ScratchBridge",
            lambda: bridge,
        )
        mp.setattr(
            "worksisyphus.core.use_cases.tracker.DEFAULT_LEADS_DIR",
            leads_dir,
        )
        code = main(
            [
                "track",
                "--company",
                "Datadog",
                "--role",
                "Systems Engineer",
                "--url",
                "https://datadoghq.com/jobs/1",
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "Tracked lead in vault:" in out
        assert (leads_dir / list_leads(leads_dir)[0]["folder"] / "jd.txt").read_text(
            encoding="utf-8"
        ) == "Scratch JD text for Datadog"


def test_cli_leads_listing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    leads_dir = tmp_path / "leads"
    track_lead(company="Google", role="Staff SWE", jd_text="Google JD", leads_dir=leads_dir)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "worksisyphus.core.use_cases.tracker.DEFAULT_LEADS_DIR",
            leads_dir,
        )
        code = main(["leads"])
        assert code == 0
        out = capsys.readouterr().out
        assert "Google" in out
        assert "Staff SWE" in out
