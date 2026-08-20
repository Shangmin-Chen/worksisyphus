from __future__ import annotations

import io
import json
from pathlib import Path

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
    assert capsys.readouterr().out == "Updated 2026-08-05_dirac_full-stack-engineer: applied -> phone_screen\n"


def test_archive_reads_jd_from_stdin(monkeypatch, tmp_path, capsys) -> None:
    import io
    from pathlib import Path

    plan = _write_plan(tmp_path, {"projects": ["proj1"]})
    recorded_args = {}

    def fake_archive(plan_path, pdf_path, jd_text, company, role="", source_url=""):
        recorded_args["plan_path"] = plan_path
        recorded_args["jd_text"] = jd_text
        recorded_args["company"] = company
        return Path("applications/2026-08-14_acme_swe")

    monkeypatch.setattr(cli, "archive_application", fake_archive)
    monkeypatch.setattr("sys.stdin", io.StringIO("Frontend engineer job description"))

    assert cli.main(["archive", "--plan", plan, "--company", "Acme", "--jd", "-"]) == 0
    assert "Archived applications/2026-08-14_acme_swe" in capsys.readouterr().out
    assert recorded_args["jd_text"] == "Frontend engineer job description"
    assert recorded_args["company"] == "Acme"


def test_archive_rejects_plan_from_stdin(capsys) -> None:
    assert cli.main(["archive", "--plan", "-", "--company", "Acme", "--jd", "-"]) == 1
    assert "error: archive requires a plan file path, not stdin" in capsys.readouterr().err


def test_archive_rejects_missing_plan_file(capsys) -> None:
    assert cli.main(["archive", "--plan", "nonexistent_plan.json", "--company", "Acme", "--jd", "-"]) == 1
    assert "error: Plan file not found" in capsys.readouterr().err


def test_cli_index(capsys) -> None:
    assert cli.main(["index"]) == 0
    out = capsys.readouterr().out
    assert "EXPERIENCES:" in out
    assert "org-a: Engineer at OrgA" in out


def test_cli_db_commands(monkeypatch, tmp_path, capsys) -> None:
    from worksisyphus import db

    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", test_db)
    monkeypatch.setattr(db, "sync_to_turso", lambda *args, **kwargs: True)

    # 1. Status before init
    assert cli.main(["db", "status"]) == 0
    assert "Database not initialized" in capsys.readouterr().out

    # 2. History before init
    assert cli.main(["db", "history"]) == 0
    assert "Database not initialized" in capsys.readouterr().out

    # 3. Init
    assert cli.main(["db", "init"]) == 0
    init_out = capsys.readouterr().out
    assert "Initialized and seeded" in init_out
    assert "Turso cloud sync: synced" in init_out

    # 4. Status after init
    assert cli.main(["db", "status"]) == 0
    status_out = capsys.readouterr().out
    assert "Database:" in status_out
    assert "Contact:" in status_out

    # 5. History after init
    assert cli.main(["db", "history"]) == 0
    hist_out = capsys.readouterr().out
    assert "Timestamp" in hist_out
    assert "Action" in hist_out

    # 6. Sync
    assert cli.main(["db", "sync"]) == 0
    sync_out = capsys.readouterr().out
    assert "Exported active database state to profile.json" in sync_out
    assert "Turso cloud sync: synced" in sync_out


def test_cli_evaluate_with_stdin_and_resume(capsys, monkeypatch) -> None:
    jd_content = "Looking for a C++ software engineer with Python and low-latency systems experience."
    monkeypatch.setattr("sys.stdin", io.StringIO(jd_content))

    ret = cli.main(["evaluate", "--resume", "resumes/Simon_Chen_Resume.pdf", "--jd", "-"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "RESUME EVALUATION REPORT" in out
    assert "Overall Match Score:" in out
    assert "SCORE BREAKDOWN:" in out


def test_cli_evaluate_with_plan(tmp_path, capsys, monkeypatch) -> None:
    plan_file = _write_plan(tmp_path, {"experiences": ["org-a"], "projects": ["proj1"]})
    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("C++ Python engineer with distributed systems experience.", encoding="utf-8")

    ret = cli.main(["evaluate", "--plan", plan_file, "--jd", str(jd_file)])
    assert ret == 0
    out = capsys.readouterr().out
    assert "RESUME EVALUATION REPORT" in out
    assert "Overall Match Score:" in out


def test_cli_evaluate_with_app(tmp_path, capsys, monkeypatch) -> None:
    app_folder = tmp_path / "applications" / "2026-08-18_testco_swe"
    app_folder.mkdir(parents=True)
    (app_folder / "jd.txt").write_text("Python backend developer.", encoding="utf-8")
    (app_folder / "meta.json").write_text('{"company": "TestCo", "status": "applied"}', encoding="utf-8")

    real_pdf = Path("resumes") / "Simon_Chen_Resume.pdf"
    if real_pdf.is_file():
        (app_folder / "Simon_Chen_Resume.pdf").write_bytes(real_pdf.read_bytes())
    else:
        pytest.skip("resumes/Simon_Chen_Resume.pdf not present")

    from worksisyphus import archive

    monkeypatch.setattr(archive, "APPLICATIONS_DIR", tmp_path / "applications")

    ret = cli.main(["evaluate", "--app", "testco_swe"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "RESUME EVALUATION REPORT: TESTCO_SWE" in out


def test_cli_evaluate_missing_jd_error(capsys) -> None:
    ret = cli.main(["evaluate", "--resume", "resumes/Simon_Chen_Resume.pdf"])
    assert ret == 1
    err = capsys.readouterr().err
    assert "error: Job description required" in err


def test_cli_evaluate_missing_app_error(capsys) -> None:
    ret = cli.main(["evaluate", "--app", "definitely_nonexistent_company"])
    assert ret == 1
    err = capsys.readouterr().err
    assert "error:" in err


def test_cli_evaluate_hackerrank_mode(capsys) -> None:
    ret = cli.main(["evaluate", "--hackerrank", "--role", "startup_product_engineer"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "HACKERRANK HIRING AGENT SCORECARD" in out
    assert "Overall Candidate Score:" in out


def test_cli_evaluate_check_upstream(capsys) -> None:
    ret = cli.main(["evaluate", "--check-upstream"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "HACKERRANK UPSTREAM SYNC STATUS" in out
    assert "interviewstreet/hiring-agent" in out
