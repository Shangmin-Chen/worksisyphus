from __future__ import annotations

import json

import pytest

from worksisyphus import cli


@pytest.fixture(autouse=True)
def _use_small_profile(small_profile, monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_profile", lambda: small_profile)


def _write_plan(tmp_path, data) -> str:
    path = tmp_path / "acme_swe.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_validate_prints_resolved_selection(tmp_path, capsys) -> None:
    plan = _write_plan(tmp_path, {"experiences": {"org-a": "all"}, "projects": {"proj1": ["p1"]}})
    assert cli.main(["validate", "--plan", plan]) == 0
    out = capsys.readouterr().out
    assert "plan OK: Simon_Chen_Resume" in out  # every tailored resume shares one output name
    assert "org-a: a1, a2, a3" in out
    assert "proj1: p1" in out
    assert "languages (2)" in out


def test_validate_rejects_unknown_slug(tmp_path, capsys) -> None:
    plan = _write_plan(tmp_path, {"experiences": {"nope": "all"}})
    assert cli.main(["validate", "--plan", plan]) == 1
    assert "error: Unknown experiences slug 'nope'" in capsys.readouterr().err


def test_validate_reads_stdin(monkeypatch, capsys) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"projects": ["proj2"]})))
    assert cli.main(["validate", "--plan", "-"]) == 0
    assert "proj2: q1" in capsys.readouterr().out


def test_status_prints_application_identifier(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "list_applications",
        lambda: [
            {
                "date": "2026-08-05",
                "company": "Dirac",
                "role": "A Full Stack Engineer Role With A Very Long Title",
                "status": "applied",
                "folder": "2026-08-05_dirac_full-stack-engineer",
            }
        ],
    )

    assert cli.main(["status"]) == 0
    output = capsys.readouterr().out
    assert "Application" in output
    assert "A Full Stack Engineer Role With… applied" in output
    assert "2026-08-05_dirac_full-stack-engineer" in output


def test_update_status_reports_transition(monkeypatch, capsys, tmp_path) -> None:
    folder = tmp_path / "2026-08-05_dirac_full-stack-engineer"
    monkeypatch.setattr(
        cli,
        "update_application_status",
        lambda app, status: (folder, "applied", status),
    )

    assert cli.main(["update-status", "--app", folder.name, "--status", "phone_screen"]) == 0
    assert (
        capsys.readouterr().out
        == "Updated 2026-08-05_dirac_full-stack-engineer: applied -> phone_screen\n"
    )
