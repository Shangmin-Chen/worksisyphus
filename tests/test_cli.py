from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from worksisyphus import cli
from worksisyphus.pipeline import PREVIEW_DIR


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
        lambda app, status, **kwargs: (folder, "applied", status),
    )

    assert cli.main(["update-status", "--app", folder.name, "--status", "phone_screen"]) == 0
    assert capsys.readouterr().out == "Updated 2026-08-05_dirac_full-stack-engineer: applied -> phone_screen\n"


def test_cli_apply_with_plan(monkeypatch, tmp_path, capsys) -> None:
    import io

    from worksisyphus.ats import ATSCheckResult
    from worksisyphus.compiler import CompileResult

    plan = _write_plan(tmp_path, {"projects": ["proj1"]})
    recorded = {}

    def fake_apply(plan_text, jd_text, company, role="", source_url="", **kwargs):
        recorded["plan_text"] = plan_text
        recorded["jd_text"] = jd_text
        recorded["company"] = company
        folder = tmp_path / "applications" / "2026-08-20_primitive_product-engineer"
        folder.mkdir(parents=True, exist_ok=True)
        pdf = folder / "Simon_Chen_Resume.pdf"
        pdf.write_bytes(b"%PDF-fake")
        return folder, CompileResult(pdf, folder / "Simon_Chen_Resume.tex", 1), ATSCheckResult(True, (), 1, 500, "text")

    monkeypatch.setattr(cli, "apply_app", fake_apply)
    monkeypatch.setattr("sys.stdin", io.StringIO("JD text content"))

    ret = cli.main(["apply", "--company", "Primitive", "--role", "Product Engineer", "--jd", "-", "--plan", plan])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Exported" in out
    assert "ATS check: passed" in out
    assert "Application created:" in out
    assert recorded["company"] == "Primitive"
    assert recorded["jd_text"] == "JD text content"


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

    # `db init` and `db sync` read profile.json from the working directory. Run them against
    # a profile this test owns: they used to silently seed from tests/fixtures/profile.json
    # whenever profile.json was absent, so a test that depends on the ambient repository
    # state is a test that passes for the wrong reason on CI.
    monkeypatch.chdir(tmp_path)
    Path("profile.json").write_text(
        json.dumps(
            {
                "contact": {
                    "name": "Real Person",
                    "email": "real.person@fastmail.dev",
                    "phone": "617-266-1810",
                    "website": "",
                    "github": "",
                    "linkedin": "",
                },
                "education": [],
                "experiences": {},
                "projects": {},
                "skills": {},
            }
        ),
        encoding="utf-8",
    )

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
    assert "Synced profile.json to SQLite and Turso cloud" in sync_out


def test_cli_db_sync_refuses_an_invalid_profile_without_touching_turso(monkeypatch, tmp_path, capsys) -> None:
    from worksisyphus import db

    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", test_db)

    pushes: list[int] = []

    def _fake_sync(*args: object, **kwargs: object) -> bool:
        pushes.append(1)
        return True

    monkeypatch.setattr(db, "sync_to_turso", _fake_sync)

    monkeypatch.chdir(tmp_path)
    fixture = Path(__file__).resolve().parent / "fixtures" / "profile.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    data["contact"]["email"] = ""
    Path("profile.json").write_text(json.dumps(data), encoding="utf-8")

    assert cli.main(["db", "sync"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "Refusing to seed the database" in err
    assert pushes == [], "the corruption must not reach the cloud copy"

    conn = db.get_connection(test_db)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "contact" not in tables, "a refused seed must not leave a half-built database behind"


def test_cli_evaluate_with_stdin_and_resume(capsys, monkeypatch, delivered_pdf) -> None:
    jd_content = "Looking for a C++ software engineer with Python and low-latency systems experience."
    monkeypatch.setattr("sys.stdin", io.StringIO(jd_content))

    ret = cli.main(["evaluate", "--resume", str(delivered_pdf), "--jd", "-"])
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


def test_cli_evaluate_with_app(tmp_path, capsys, monkeypatch, delivered_pdf) -> None:
    app_folder = tmp_path / "applications" / "2026-08-18_testco_swe"
    app_folder.mkdir(parents=True)
    (app_folder / "jd.txt").write_text("Python backend developer.", encoding="utf-8")
    (app_folder / "meta.json").write_text('{"company": "TestCo", "status": "applied"}', encoding="utf-8")

    (app_folder / "Simon_Chen_Resume.pdf").write_bytes(delivered_pdf.read_bytes())

    from worksisyphus import application

    monkeypatch.setattr(application, "APPLICATIONS_DIR", tmp_path / "applications")

    ret = cli.main(["evaluate", "--app", "testco_swe"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "RESUME EVALUATION REPORT: TESTCO_SWE" in out


def test_cli_evaluate_missing_jd_error(capsys, delivered_pdf) -> None:
    ret = cli.main(["evaluate", "--resume", str(delivered_pdf)])
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


def test_cli_evaluate_profile_mode(capsys) -> None:
    ret = cli.main(["evaluate", "--profile", "--hackerrank", "--role", "software_engineer"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "HACKERRANK HIRING AGENT SCORECARD" in out
    assert "Overall Candidate Score:" in out


def test_cli_evaluate_profile_with_jd(tmp_path, capsys) -> None:
    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("Backend engineer with Python, C++, and Distributed Systems.", encoding="utf-8")
    ret = cli.main(["evaluate", "--profile", "--jd", str(jd_file)])
    assert ret == 0
    out = capsys.readouterr().out
    assert "RESUME EVALUATION REPORT: PROFILE_JSON" in out
    assert "Overall Match Score:" in out


def test_cli_evaluate_check_upstream(capsys) -> None:
    ret = cli.main(["evaluate", "--check-upstream"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "HACKERRANK UPSTREAM SYNC STATUS" in out
    assert "interviewstreet/hiring-agent" in out


def test_cli_optimize_command(tmp_path, capsys) -> None:
    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("Looking for a distributed systems engineer with C++ and Python.", encoding="utf-8")
    out_file = tmp_path / "optimal_plan.json"

    ret = cli.main(["optimize", "--jd", str(jd_file), "--role", "systems_engineer", "--output", str(out_file)])
    assert ret == 0
    out = capsys.readouterr().out
    assert "HACKERRANK KNAPSACK OPTIMIZER REPORT" in out
    assert out_file.is_file()


def test_cli_tailor_invokes_pipeline(monkeypatch, tmp_path) -> None:
    plan = _write_plan(tmp_path, {"projects": ["proj1"]})
    recorded = {}

    def fake_tailor(plan_text, plan_name="custom", pdf_dir=None, log=None):
        recorded["pdf_dir"] = pdf_dir
        recorded["plan_text"] = plan_text
        recorded["plan_name"] = plan_name

    monkeypatch.setattr(cli, "tailor", fake_tailor)

    assert cli.main(["tailor", "--plan", plan]) == 0
    assert recorded["plan_name"] == "acme_swe"
    # tailor is a preview command: it must never default into applications/, where delivered
    # resumes live.
    assert recorded["pdf_dir"] == PREVIEW_DIR


def test_cli_apply_with_optimizer(monkeypatch, tmp_path, capsys) -> None:
    import io

    from worksisyphus.ats import ATSCheckResult
    from worksisyphus.compiler import CompileResult

    recorded = {}

    def fake_apply(plan_text, jd_text, company, role="", source_url="", **kwargs):
        recorded["plan_text"] = plan_text
        recorded["jd_text"] = jd_text
        recorded["company"] = company
        folder = tmp_path / "applications" / "2026-08-20_primitive_product-engineer"
        folder.mkdir(parents=True, exist_ok=True)
        pdf = folder / "Simon_Chen_Resume.pdf"
        pdf.write_bytes(b"%PDF-fake")
        return folder, CompileResult(pdf, folder / "Simon_Chen_Resume.tex", 1), ATSCheckResult(True, (), 1, 500, "text")

    monkeypatch.setattr(cli, "apply_app", fake_apply)
    monkeypatch.setattr("sys.stdin", io.StringIO("Full-stack engineer building with Python and TypeScript."))

    ret = cli.main(["apply", "--company", "Primitive", "--role", "product_engineer", "--jd", "-", "--no-sync"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Exported" in out
    assert "ATS check: passed" in out
    assert recorded["company"] == "Primitive"
    assert "projects" in recorded["plan_text"]


def test_cli_apply_surfaces_optimizer_failure_as_an_error(monkeypatch, capsys) -> None:
    """Plan-less apply must report an optimizer failure, not spill a traceback.

    `apply` without --plan runs the optimizer, which raises OptimizerError rather than handing
    back an unscored plan. The CLI contract is exit code 1 and a single `error: ...` line on
    stderr; nothing covered that path.
    """
    import io

    import worksisyphus.optimizer as optimizer_module

    def failing_optimize(profile, jd_text, role_name="software_engineer"):
        raise optimizer_module.OptimizerError("no candidate plan could be scored")

    def unreachable_apply(*args, **kwargs):
        raise AssertionError("apply must not run when the optimizer produced no plan")

    monkeypatch.setattr(optimizer_module, "optimize_plan", failing_optimize)
    monkeypatch.setattr(cli, "apply_app", unreachable_apply)
    monkeypatch.setattr("sys.stdin", io.StringIO("Backend engineer, distributed systems."))

    assert cli.main(["apply", "--company", "Primitive", "--jd", "-", "--no-sync"]) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("error: ")
    assert "no candidate plan could be scored" in captured.err
    assert "Traceback" not in captured.err


def test_cli_tailor_refuses_an_invalid_contact(monkeypatch, tmp_path, capsys, invalid_contact_profile) -> None:
    import worksisyphus.pipeline as pipeline_module

    compiled: list[str] = []

    def exploding_compile(tex, name, tex_dir, pdf_dir):
        compiled.append(name)
        raise AssertionError("compilation must not be reached for an invalid contact")

    monkeypatch.setattr(pipeline_module, "compile_tex", exploding_compile)
    monkeypatch.setattr(pipeline_module, "load_profile", lambda _path: invalid_contact_profile)

    plan = _write_plan(tmp_path, {"projects": ["proj1"]})
    out_dir = tmp_path / "preview"

    assert cli.main(["tailor", "--plan", plan, "--output", str(out_dir)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "empty" in err
    assert compiled == []
    assert list(out_dir.glob("*.pdf")) == []
