"""Unit and integration tests for Venue 2 (apply --url and apply --lead)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from worksisyphus import CompileResult
from worksisyphus.adapters.inbound.cli.commands import main
from worksisyphus.ats import ATSCheckResult
from worksisyphus.core.domain.ingestion import RawJobPayload
from worksisyphus.core.use_cases.tracker import track_lead
from worksisyphus.gates import GateResult


def _fake_compile(tex: str, name: str, tex_dir: Path, pdf_dir: Path) -> CompileResult:
    pdf_path = pdf_dir / f"{name}.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    tex_path = tex_dir / f"{name}.tex"
    tex_path.write_text(tex, encoding="utf-8")
    return CompileResult(pdf_path=pdf_path, tex_path=tex_path, pages=1)


def _fake_run_gates(pdf_path: Path, **kwargs: object) -> tuple[tuple[GateResult, ...], ATSCheckResult]:
    return (
        (GateResult("ATS Extraction & Page Count Gate", True, ()),),
        ATSCheckResult(
            passed=True,
            problems=(),
            pages=1,
            word_count=450,
            text="Simon Chen Software Engineer Distributed Systems",
        ),
    )


def test_apply_with_url_fetches_and_compiles(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    apps_dir = tmp_path / "applications"

    mock_payload = RawJobPayload(
        url="https://stripe.com/jobs/123",
        raw_content="<html><body><h1>Distributed Systems Engineer</h1><p>We build global financial infra in Go and Rust.</p></body></html>",
        content_type="text/html",
        source_hint="web",
        fetched_at="2026-09-23T20:00:00Z",
    )

    import worksisyphus.core.use_cases.application as app_module
    import worksisyphus.core.use_cases.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", _fake_compile)
    monkeypatch.setattr(app_module, "run_resume_gates", _fake_run_gates)

    with (
        patch(
            "worksisyphus.adapters.inbound.cli.handlers.apply.HttpRawFetcher.fetch",
            return_value=mock_payload,
        ),
        patch(
            "worksisyphus.core.use_cases.application._resolve_applications_dir",
            return_value=apps_dir,
        ),
    ):
        code = main(
            [
                "apply",
                "--company",
                "Stripe",
                "--role",
                "Infra Engineer",
                "--url",
                "https://stripe.com/jobs/123",
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "Application created:" in out

        # Verify application files
        app_folders = list(apps_dir.iterdir())
        assert len(app_folders) == 1
        app_folder = app_folders[0]
        assert (app_folder / "jd.txt").is_file()
        assert "Distributed Systems Engineer" in (app_folder / "jd.txt").read_text(encoding="utf-8")
        assert (app_folder / "meta.json").is_file()
        meta = json.loads((app_folder / "meta.json").read_text(encoding="utf-8"))
        assert meta["company"] == "Stripe"
        assert meta["source_url"] == "https://stripe.com/jobs/123"


def test_apply_with_lead_stem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    leads_dir = tmp_path / "leads"
    apps_dir = tmp_path / "applications"

    lead_path = track_lead(
        company="Datadog",
        role="Core Systems SWE",
        jd_text="Datadog is building telemetry ingest systems in Go.",
        url="https://datadoghq.com/jobs/123",
        questions=[{"id": "q1", "prompt": "Years of Go experience?"}],
        leads_dir=leads_dir,
    )

    import worksisyphus.core.use_cases.application as app_module
    import worksisyphus.core.use_cases.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", _fake_compile)
    monkeypatch.setattr(app_module, "run_resume_gates", _fake_run_gates)

    with (
        patch(
            "worksisyphus.core.use_cases.tracker.DEFAULT_LEADS_DIR",
            leads_dir,
        ),
        patch(
            "worksisyphus.core.use_cases.application._resolve_applications_dir",
            return_value=apps_dir,
        ),
    ):
        code = main(
            [
                "apply",
                "--lead",
                lead_path.name,
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "Application created:" in out

        # Check lead status updated to applied
        lead_meta = json.loads((lead_path / "meta.json").read_text(encoding="utf-8"))
        assert lead_meta["status"] == "applied"

        # Check application folder created with jd, questions, meta
        app_folders = list(apps_dir.iterdir())
        assert len(app_folders) == 1
        app_folder = app_folders[0]
        assert (app_folder / "jd.txt").is_file()
        assert (app_folder / "questions.json").is_file()
        q_data = json.loads((app_folder / "questions.json").read_text(encoding="utf-8"))
        assert q_data[0]["id"] == "q1"
