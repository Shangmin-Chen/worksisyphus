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
    assert "plan OK: acme_swe_resume" in out  # name falls back to the plan filename
    assert "org-a: a1, a2, a3" in out
    assert "proj1: p1" in out
    assert "languages (2)" in out


def test_validate_rejects_unknown_slug(tmp_path, capsys) -> None:
    plan = _write_plan(tmp_path, {"experiences": {"nope": "all"}})
    assert cli.main(["validate", "--plan", plan]) == 1
    assert "error: Unknown experiences slug 'nope'" in capsys.readouterr().err


def test_validate_reads_stdin(monkeypatch, capsys) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"name": "x", "projects": ["proj2"]})))
    assert cli.main(["validate", "--plan", "-"]) == 0
    assert "proj2: q1" in capsys.readouterr().out
