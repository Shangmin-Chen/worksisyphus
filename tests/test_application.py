from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from worksisyphus import CompileResult, apply
from worksisyphus.application import list_applications, resolve_application_folder, slugify, update_application_status
from worksisyphus.ats import ATSCheckResult
from worksisyphus.gates import GateResult


def test_slugify() -> None:
    assert slugify("Primitive") == "primitive"
    assert slugify("Product Engineer") == "product-engineer"
    assert slugify("  Founding SWE (AI / Systems)  ") == "founding-swe-ai-systems"


def test_apply_compiles_freezes_and_validates(small_profile, monkeypatch, tmp_path) -> None:
    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        pdf_path = pdf_dir / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)

    def fake_run_gates(pdf_path, **kwargs) -> tuple[tuple[GateResult, ...], ATSCheckResult]:
        return (
            (GateResult("ATS Extraction & Page Count Gate", True, ()),),
            ATSCheckResult(passed=True, problems=(), pages=1, word_count=450, text="Simon Chen"),
        )

    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", fake_compile)
    monkeypatch.setattr(pipe_module, "load_profile", lambda _path: small_profile)
    monkeypatch.setattr(app_module, "run_resume_gates", fake_run_gates)

    plan_text = json.dumps({"experiences": {"org-a": ["a1"]}, "projects": {"proj1": ["p1"]}})
    apps_dir = tmp_path / "applications"

    folder, _comp_res, ats_res = apply(
        plan_text=plan_text,
        jd_text="Backend engineer role",
        company="Acme Corp",
        role="Product Engineer",
        when=date(2026, 8, 20),
        profile=small_profile,
        applications_dir=apps_dir,
        sync_cloud=False,
    )

    assert folder == apps_dir / "2026-08-20_acme-corp_product-engineer"
    assert (folder / "Simon_Chen_Resume.pdf").is_file()
    assert (folder / "plan.json").is_file()
    assert (folder / "jd.txt").read_text() == "Backend engineer role\n"
    assert ats_res.passed is True

    meta = json.loads((folder / "meta.json").read_text())
    assert meta["company"] == "Acme Corp"
    assert meta["role"] == "Product Engineer"
    assert meta["status"] == "applied"


def test_apply_rejects_when_quality_gate_fails_and_cleans_up_atomically(small_profile, monkeypatch, tmp_path) -> None:
    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        pdf_path = pdf_dir / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)

    def fake_failing_gates(pdf_path, **kwargs) -> tuple[tuple[GateResult, ...], ATSCheckResult]:
        return (
            (GateResult("No-GPA Gate", False, ("Found GPA reference: ['3.9/4.0']",)),),
            ATSCheckResult(passed=True, problems=(), pages=1, word_count=450, text="Simon Chen"),
        )

    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", fake_compile)
    monkeypatch.setattr(app_module, "run_resume_gates", fake_failing_gates)

    apps_dir = tmp_path / "applications"
    with pytest.raises(RuntimeError, match="Quality gate check failed"):
        apply(
            plan_text=json.dumps({"experiences": {"org-a": ["a1"]}}),
            jd_text="Backend engineer role",
            company="Acme Corp",
            role="Product Engineer",
            when=date(2026, 8, 20),
            profile=small_profile,
            applications_dir=apps_dir,
            sync_cloud=False,
        )

    # Verify atomic rollback: nothing published into applications_dir
    assert not (apps_dir / "2026-08-20_acme-corp_product-engineer").exists()
    # No staging residue is left inside applications/
    assert list(apps_dir.iterdir()) == []


def test_apply_gate_failure_leaves_existing_applications_intact(small_profile, monkeypatch, tmp_path) -> None:
    """A failed build must not disturb any already-delivered application."""

    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        pdf_path = pdf_dir / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF-fails-no-gpa-gate")
        return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)

    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", fake_compile)
    monkeypatch.setattr(
        app_module,
        "run_resume_gates",
        lambda *a, **kw: (
            (GateResult("No-GPA Gate", False, ("Found GPA reference: ['3.9/4.0']",)),),
            ATSCheckResult(True, (), 1, 100, "text"),
        ),
    )

    apps_dir = tmp_path / "applications"
    apps_dir.mkdir(parents=True)
    prior = apps_dir / "2026-08-19_other-co_swe"
    prior.mkdir()
    (prior / "Simon_Chen_Resume.pdf").write_bytes(b"%PDF-previously-delivered-good-resume")
    (prior / "meta.json").write_text(json.dumps({"company": "Other Co", "status": "applied"}), encoding="utf-8")
    before = {q.name: q.read_bytes() for q in prior.iterdir()}

    with pytest.raises(RuntimeError, match="Quality gate check failed"):
        apply(
            plan_text=json.dumps({"experiences": {"org-a": ["a1"]}}),
            jd_text="Backend engineer role",
            company="Acme Corp",
            role="Product Engineer",
            when=date(2026, 8, 20),
            profile=small_profile,
            applications_dir=apps_dir,
            sync_cloud=False,
        )

    # Delivered resumes exist only inside applications/. A failed build must not touch any of
    # them, and must not publish or leave residue of its own.
    assert {q.name: q.read_bytes() for q in prior.iterdir()} == before
    assert sorted(q.name for q in apps_dir.iterdir()) == ["2026-08-19_other-co_swe"]


def test_apply_can_be_retried_immediately_after_failure(small_profile, monkeypatch, tmp_path) -> None:
    """A failed build must not consume the folder slot for that company/role/date."""
    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        pdf_path = pdf_dir / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)

    monkeypatch.setattr(pipe_module, "compile_tex", fake_compile)
    monkeypatch.setattr(
        app_module,
        "run_resume_gates",
        lambda *a, **kw: (
            (GateResult("No-GPA Gate", False, ("nope",)),),
            ATSCheckResult(True, (), 1, 100, "text"),
        ),
    )

    apps_dir = tmp_path / "applications"
    kwargs = dict(
        plan_text=json.dumps({"experiences": {"org-a": ["a1"]}}),
        jd_text="Backend engineer role",
        company="Acme Corp",
        role="Product Engineer",
        when=date(2026, 8, 20),
        profile=small_profile,
        applications_dir=apps_dir,
        sync_cloud=False,
    )
    with pytest.raises(RuntimeError):
        apply(**kwargs)

    # Same arguments now succeed: the failed attempt reserved nothing.
    monkeypatch.setattr(
        app_module,
        "run_resume_gates",
        lambda *a, **kw: ((GateResult("ATS", True, ()),), ATSCheckResult(True, (), 1, 100, "text")),
    )
    folder, compile_res, _ats = apply(**kwargs)
    assert folder == apps_dir / "2026-08-20_acme-corp_product-engineer"
    # The returned compile result points at the published PDF, not a staging path that no longer exists.
    assert compile_res.pdf_path == folder / "Simon_Chen_Resume.pdf"
    assert compile_res.pdf_path.is_file()


def test_list_applications_ignores_staging_directories(tmp_path) -> None:
    apps_dir = tmp_path / "applications"
    (apps_dir / ".staging-abc123").mkdir(parents=True)
    real = apps_dir / "2026-08-20_acme_swe"
    real.mkdir()
    (real / "meta.json").write_text(json.dumps({"company": "Acme", "status": "applied"}), encoding="utf-8")

    apps = list_applications(applications_dir=apps_dir)
    assert [a["folder"] for a in apps] == ["2026-08-20_acme_swe"]


def test_apply_rejects_empty_jd(tmp_path) -> None:
    with pytest.raises(ValueError, match="jd_text is empty"):
        apply(
            plan_text="{}",
            jd_text="   ",
            company="Acme",
            applications_dir=tmp_path / "applications",
        )


def test_apply_rejects_empty_company(tmp_path) -> None:
    with pytest.raises(ValueError, match="company name is required"):
        apply(
            plan_text="{}",
            jd_text="JD text",
            company="   ",
            applications_dir=tmp_path / "applications",
        )


def test_apply_rejects_empty_plan(tmp_path) -> None:
    with pytest.raises(ValueError, match="Plan is empty"):
        apply(
            plan_text="   ",
            jd_text="JD text",
            company="Acme",
            applications_dir=tmp_path / "applications",
        )


def test_apply_is_immutable(small_profile, monkeypatch, tmp_path) -> None:
    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        pdf_path = pdf_dir / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)

    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", fake_compile)
    monkeypatch.setattr(
        app_module,
        "run_resume_gates",
        lambda *a, **kw: ((GateResult("ATS", True, ()),), ATSCheckResult(True, (), 1, 100, "text")),
    )

    plan_text = json.dumps({"experiences": {"org-a": ["a1"]}})
    apps_dir = tmp_path / "applications"

    apply(
        plan_text=plan_text,
        jd_text="JD text",
        company="Acme",
        role="SWE",
        when=date(2026, 8, 20),
        profile=small_profile,
        applications_dir=apps_dir,
        sync_cloud=False,
    )

    with pytest.raises(FileExistsError, match="immutable"):
        apply(
            plan_text=plan_text,
            jd_text="JD text",
            company="Acme",
            role="SWE",
            when=date(2026, 8, 20),
            profile=small_profile,
            applications_dir=apps_dir,
            sync_cloud=False,
        )


def test_list_and_update_application_status(small_profile, monkeypatch, tmp_path) -> None:
    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        pdf_path = pdf_dir / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)

    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", fake_compile)
    monkeypatch.setattr(
        app_module,
        "run_resume_gates",
        lambda *a, **kw: ((GateResult("ATS", True, ()),), ATSCheckResult(True, (), 1, 100, "text")),
    )

    apps_dir = tmp_path / "applications"
    folder, _, _ = apply(
        plan_text=json.dumps({"experiences": {"org-a": ["a1"]}}),
        jd_text="jd text",
        company="Acme",
        role="SWE",
        when=date(2026, 7, 11),
        profile=small_profile,
        applications_dir=apps_dir,
        sync_cloud=False,
    )
    app_list = list_applications(applications_dir=apps_dir)
    assert len(app_list) == 1
    assert app_list[0]["company"] == "Acme"
    assert app_list[0]["status"] == "applied"

    target, old, new = update_application_status(
        "acme_swe", "phone_screen", applications_dir=apps_dir, sync_cloud=False
    )
    assert target == folder
    assert old == "applied"
    assert new == "phone_screen"

    updated_meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    assert updated_meta["status"] == "phone_screen"


def test_update_status_rejects_ambiguous_stem_and_partial_match(small_profile, monkeypatch, tmp_path) -> None:
    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        pdf_path = pdf_dir / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)

    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", fake_compile)
    monkeypatch.setattr(
        app_module,
        "run_resume_gates",
        lambda *a, **kw: ((GateResult("ATS", True, ()),), ATSCheckResult(True, (), 1, 100, "text")),
    )

    apps_dir = tmp_path / "applications"
    first, _, _ = apply(
        plan_text=json.dumps({"experiences": {"org-a": ["a1"]}}),
        jd_text="jd",
        company="Acme",
        role="SWE",
        when=date(2026, 7, 11),
        profile=small_profile,
        applications_dir=apps_dir,
        sync_cloud=False,
    )
    second, _, _ = apply(
        plan_text=json.dumps({"experiences": {"org-a": ["a1"]}}),
        jd_text="jd",
        company="Acme",
        role="SWE",
        when=date(2026, 7, 12),
        profile=small_profile,
        applications_dir=apps_dir,
        sync_cloud=False,
    )

    with pytest.raises(ValueError, match="ambiguous"):
        update_application_status("acme_swe", "phone_screen", applications_dir=apps_dir, sync_cloud=False)
    with pytest.raises(FileNotFoundError, match="No application folder"):
        update_application_status("acme", "phone_screen", applications_dir=apps_dir, sync_cloud=False)
    with pytest.raises(ValueError, match="must not be empty"):
        update_application_status("", "phone_screen", applications_dir=apps_dir, sync_cloud=False)

    target, old, new = update_application_status(
        first.name, "phone_screen", applications_dir=apps_dir, sync_cloud=False
    )
    assert (target, old, new) == (first, "applied", "phone_screen")
    assert not (first / "meta.json.tmp").exists()
    assert json.loads((second / "meta.json").read_text(encoding="utf-8"))["status"] == "applied"


def test_list_applications_reports_invalid_metadata(tmp_path) -> None:
    folder = tmp_path / "applications" / "2026-07-11_acme_swe"
    folder.mkdir(parents=True)
    (folder / "meta.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match=r"2026-07-11_acme_swe.*JSON object"):
        list_applications(tmp_path / "applications")


def test_resolve_application_folder_errors(tmp_path) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        resolve_application_folder("  ", applications_dir=tmp_path / "applications")
    with pytest.raises(FileNotFoundError, match="No application folder"):
        resolve_application_folder("nonexistent", applications_dir=tmp_path / "applications")


def _fake_gates_ok():
    return lambda *a, **kw: (
        (GateResult("ATS", True, ()),),
        ATSCheckResult(True, (), 1, 400, "Simon Chen Python React distributed systems latency"),
    )


def test_apply_records_the_hackerrank_evaluation(small_profile, monkeypatch, tmp_path) -> None:
    """Every application must carry the score that was true when it was sent."""

    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        pdf_path = pdf_dir / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)

    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", fake_compile)
    monkeypatch.setattr(app_module, "run_resume_gates", _fake_gates_ok())

    folder, _c, _a = apply(
        plan_text=json.dumps({"experiences": {"org-a": ["a1"]}}),
        jd_text="React frontend, Python backend, and infrastructure.",
        company="Acme Corp",
        role="Founding Product Engineer",
        when=date(2026, 8, 20),
        profile=small_profile,
        applications_dir=tmp_path / "applications",
        sync_cloud=False,
    )

    meta = json.loads((folder / "meta.json").read_text())
    ev = meta["evaluation"]
    assert ev["role_rubric"] == "founding_product_engineer"
    assert ev["total_score"] > 0
    assert len(ev["scores"]) == 3
    assert ev["evaluated_at"]


def test_backfill_is_idempotent_and_respects_overwrite(small_profile, monkeypatch, tmp_path) -> None:
    from worksisyphus.application import backfill_evaluations

    apps = tmp_path / "applications"
    folder = apps / "2026-08-01_oldco_swe"
    folder.mkdir(parents=True)
    (folder / "meta.json").write_text(json.dumps({"company": "OldCo", "role": "SWE", "status": "applied"}))
    (folder / "jd.txt").write_text("Python backend engineer.")
    (folder / "Simon_Chen_Resume.pdf").write_bytes(b"%PDF-fake")

    import worksisyphus.application as app_module

    monkeypatch.setattr(app_module, "check_pdf_ats", lambda p, **kw: ATSCheckResult(True, (), 1, 400, "Python"))

    first = backfill_evaluations(applications_dir=apps)
    assert [name for name, _ in first] == ["2026-08-01_oldco_swe"]
    stamp = json.loads((folder / "meta.json").read_text())["evaluation"]["evaluated_at"]

    # Already scored: a second run must leave it alone.
    assert backfill_evaluations(applications_dir=apps) == []
    assert json.loads((folder / "meta.json").read_text())["evaluation"]["evaluated_at"] == stamp

    # ...unless explicitly told to re-score.
    assert len(backfill_evaluations(applications_dir=apps, overwrite=True)) == 1


def _fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
    pdf_path = pdf_dir / f"{name}.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)


def _passing_gates(pdf_path, **kwargs) -> tuple[tuple[GateResult, ...], ATSCheckResult]:
    return (
        (GateResult("ATS Extraction & Page Count Gate", True, ()),),
        ATSCheckResult(passed=True, problems=(), pages=1, word_count=450, text="Simon Chen"),
    )


def _seed_db(path, contact: dict | None) -> None:
    """A temp database with schema, optionally carrying a contact row."""
    from worksisyphus.db import get_connection, init_schema

    conn = get_connection(path)
    try:
        init_schema(conn)
        if contact is not None:
            conn.execute(
                "INSERT OR REPLACE INTO contact (id, name, email, phone, website, github, linkedin) "
                "VALUES (1, ?, ?, ?, ?, ?, ?)",
                (
                    contact["name"],
                    contact["email"],
                    contact["phone"],
                    contact.get("website", ""),
                    contact.get("github", ""),
                    contact.get("linkedin", ""),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _apply_kwargs(apps_dir, profile, **overrides):
    kwargs = dict(
        plan_text=json.dumps({"experiences": {"org-a": ["a1"]}, "projects": {"proj1": ["p1"]}}),
        jd_text="Backend engineer role",
        company="Acme Corp",
        role="Product Engineer",
        when=date(2026, 8, 20),
        profile=profile,
        applications_dir=apps_dir,
        sync_cloud=False,
    )
    kwargs.update(overrides)
    return kwargs


def test_apply_refuses_a_placeholder_contact_before_compiling(placeholder_profile, monkeypatch, tmp_path) -> None:
    """The incident, reproduced: a full profile whose contact block is scrubbed.

    Every quality gate passed for four resumes built this way, because each gate compares the
    PDF against the profile that rendered it. apply() now checks the profile against the
    rules first, before pdflatex is ever invoked.
    """
    import worksisyphus.pipeline as pipe_module

    compiled: list[str] = []

    def exploding_compile(tex, name, tex_dir, pdf_dir):
        compiled.append(name)
        return _fake_compile(tex, name, tex_dir, pdf_dir)

    monkeypatch.setattr(pipe_module, "compile_tex", exploding_compile)

    apps_dir = tmp_path / "applications"
    with pytest.raises(ValueError, match="placeholder"):
        apply(**_apply_kwargs(apps_dir, placeholder_profile))

    assert compiled == [], "contact validation must run before any LaTeX compilation"
    assert not apps_dir.exists(), "a rejected apply must not even create applications/"


def test_apply_refuses_when_contact_disagrees_with_the_database(small_profile, monkeypatch, tmp_path) -> None:
    """The check that would have caught the incident: the database held the real contact."""
    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", _fake_compile)
    monkeypatch.setattr(app_module, "run_resume_gates", _passing_gates)

    db_file = tmp_path / "worksisyphus.db"
    _seed_db(
        db_file,
        {"name": "Simon Chen", "email": "real.simon@fixture.test", "phone": "617-201-4477"},
    )

    apps_dir = tmp_path / "applications"
    with pytest.raises(ValueError) as excinfo:
        apply(**_apply_kwargs(apps_dir, small_profile, db_path=db_file))

    message = str(excinfo.value)
    assert "contact.email" in message
    assert small_profile.contact.email in message, "the error must name the profile value"
    assert "real.simon@fixture.test" in message, "the error must name the database value"
    assert not (apps_dir / "2026-08-20_acme-corp_product-engineer").exists()


def test_apply_accepts_a_contact_matching_the_database(small_profile, monkeypatch, tmp_path) -> None:
    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", _fake_compile)
    monkeypatch.setattr(app_module, "run_resume_gates", _passing_gates)

    db_file = tmp_path / "worksisyphus.db"
    contact = small_profile.contact
    _seed_db(db_file, {"name": contact.name, "email": contact.email, "phone": contact.phone})

    apps_dir = tmp_path / "applications"
    folder, _compile_result, _ats = apply(**_apply_kwargs(apps_dir, small_profile, db_path=db_file))
    assert (folder / "Simon_Chen_Resume.pdf").is_file()


def test_apply_names_a_placeholder_database_instead_of_reporting_a_bare_mismatch(
    small_profile, monkeypatch, tmp_path
) -> None:
    """Defence in depth on the other side of the cross-check.

    A database holding placeholders already blocked the build -- as a mismatch, since the
    profile was validated first and therefore cannot agree with it. But "contact details
    disagree" points the reader at both copies equally, and the correct repair here is the
    opposite of the one the mismatch text leads with. Validating the database side turns that
    into the specific diagnosis, and the right direction: profile.json is known good at this
    point, so the fix is `db sync`, never `db export-profile`.
    """
    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", _fake_compile)
    monkeypatch.setattr(app_module, "run_resume_gates", _passing_gates)

    db_file = tmp_path / "worksisyphus.db"
    _seed_db(db_file, {"name": "Simon Chen", "email": "simon@example.com", "phone": "555-555-5555"})

    apps_dir = tmp_path / "applications"
    with pytest.raises(ValueError) as excinfo:
        apply(**_apply_kwargs(apps_dir, small_profile, db_path=db_file))

    message = str(excinfo.value)
    assert "placeholder" in message
    assert "simon@example.com" in message
    assert "db sync" in message, "profile.json is the good copy here; the database is repaired from it"
    # export-profile writes the database over profile.json, which here would destroy the last
    # good contact block: it may appear only inside an explicit warning, never as advice.
    for sentence in re.split(r"(?<=[.]) ", message):
        if "db export-profile" in sentence:
            assert "do not" in sentence.lower(), f"the message advises export-profile: {sentence}"
    assert not apps_dir.exists(), "a refused build must publish nothing"


def test_cross_check_still_reports_a_plain_mismatch_between_two_valid_contacts(small_profile, tmp_path) -> None:
    """Validating the database side must not swallow the ordinary disagreement case."""
    from worksisyphus.application import cross_check_contact_against_db

    db_file = tmp_path / "worksisyphus.db"
    _seed_db(db_file, {"name": "Simon Chen", "email": "real.simon@fixture.test", "phone": "617-201-4477"})

    with pytest.raises(ValueError) as excinfo:
        cross_check_contact_against_db(small_profile.contact, db_file)

    message = str(excinfo.value)
    assert "Contact details disagree" in message
    assert "placeholder" not in message


def test_apply_skips_the_cross_check_loudly_when_the_database_is_absent(small_profile, monkeypatch, tmp_path) -> None:
    """A missing database must not become the next silent fallback: skip, but say so."""
    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", _fake_compile)
    monkeypatch.setattr(app_module, "run_resume_gates", _passing_gates)

    messages: list[str] = []
    apps_dir = tmp_path / "applications"
    folder, _compile_result, _ats = apply(
        **_apply_kwargs(apps_dir, small_profile, db_path=tmp_path / "absent.db", log=messages.append)
    )

    assert (folder / "Simon_Chen_Resume.pdf").is_file()
    assert any("cross-check skipped" in m and "absent.db" in m for m in messages), messages


def test_apply_skips_the_cross_check_when_the_database_has_no_contact_row(small_profile, monkeypatch, tmp_path) -> None:
    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", _fake_compile)
    monkeypatch.setattr(app_module, "run_resume_gates", _passing_gates)

    db_file = tmp_path / "worksisyphus.db"
    _seed_db(db_file, None)

    messages: list[str] = []
    apps_dir = tmp_path / "applications"
    apply(**_apply_kwargs(apps_dir, small_profile, db_path=db_file, log=messages.append))
    assert any("no contact row" in m for m in messages), messages


def test_apply_cross_check_is_skipped_for_non_default_application_dirs(small_profile, tmp_path) -> None:
    """A scratch build must never be cross-checked against -- or recorded in -- the live store."""
    from worksisyphus.application import _resolve_db_path

    assert _resolve_db_path(None, tmp_path / "applications") is None
    assert _resolve_db_path(None, Path("applications")) == Path("worksisyphus.db")


def test_resolve_db_path_normalizes_an_equivalent_absolute_applications_dir() -> None:
    """The default applications/ dir must be recognised however it is spelled.

    ``Path.__eq__`` compares strings, so the absolute form of the very same directory compared
    unequal and silently turned off both the contact cross-check and DB persistence -- no
    error, no log. Not reachable from today's CLI, which always passes None, but the
    incident-preventing check is now routed through this comparison.
    """
    from worksisyphus.application import _resolve_db_path

    relative = _resolve_db_path(None, Path("applications"))
    absolute = _resolve_db_path(None, Path.cwd() / "applications")
    assert relative == Path("worksisyphus.db")
    assert absolute == relative, "an equivalent absolute path must resolve to the same database"
    assert _resolve_db_path(None, Path("./applications/")) == relative


def test_apply_records_that_the_contact_was_cross_checked(small_profile, monkeypatch, tmp_path) -> None:
    """meta.json states that the contact was verified against the database.

    The cross-check's outcome used to exist only as a bool apply() threw away plus a string
    handed to `log`, which defaults to silence. A reader of an application folder could not
    tell a verified contact from an unverifiable one; meta.json is the frozen record of what
    was true when the resume was sent, so the answer belongs there.
    """
    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", _fake_compile)
    monkeypatch.setattr(app_module, "run_resume_gates", _passing_gates)

    db_file = tmp_path / "worksisyphus.db"
    contact = small_profile.contact
    _seed_db(db_file, {"name": contact.name, "email": contact.email, "phone": contact.phone})

    apps_dir = tmp_path / "applications"
    folder, _compile_result, _ats = apply(**_apply_kwargs(apps_dir, small_profile, db_path=db_file))

    verification = json.loads((folder / "meta.json").read_text(encoding="utf-8"))["contact_verification"]
    assert verification["rules_checked"] is True
    assert verification["cross_checked_against_db"] is True
    assert verification["database"] == str(db_file)
    assert verification["skip_reason"] == ""


def test_apply_records_why_the_cross_check_was_skipped(small_profile, monkeypatch, tmp_path) -> None:
    """A skip is written down with its reason, so it can never read as a pass.

    Reproduces the reviewer's case: a nonexistent db_path and no log= at all. The run still
    succeeds -- the rule checks protect a fresh clone -- but the folder says so out loud.
    """
    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", _fake_compile)
    monkeypatch.setattr(app_module, "run_resume_gates", _passing_gates)

    missing_db = tmp_path / "absent.db"
    apps_dir = tmp_path / "applications"
    folder, _compile_result, _ats = apply(**_apply_kwargs(apps_dir, small_profile, db_path=missing_db))

    verification = json.loads((folder / "meta.json").read_text(encoding="utf-8"))["contact_verification"]
    assert verification["rules_checked"] is True
    assert verification["cross_checked_against_db"] is False
    assert "absent.db" in verification["skip_reason"]


def test_failed_apply_publishes_nothing_at_all(small_profile, monkeypatch, tmp_path) -> None:
    """A failure inside the staging window leaves no folder, no staging residue, and no DB row."""
    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    def failing_gates(pdf_path, **kwargs) -> tuple[tuple[GateResult, ...], ATSCheckResult]:
        return (
            (GateResult("No-GPA Gate", False, ("Found GPA reference: ['3.9/4.0']",)),),
            ATSCheckResult(passed=True, problems=(), pages=1, word_count=450, text="Simon Chen"),
        )

    monkeypatch.setattr(pipe_module, "compile_tex", _fake_compile)
    monkeypatch.setattr(app_module, "run_resume_gates", failing_gates)

    db_file = tmp_path / "worksisyphus.db"
    contact = small_profile.contact
    _seed_db(db_file, {"name": contact.name, "email": contact.email, "phone": contact.phone})

    apps_dir = tmp_path / "applications"
    with pytest.raises(RuntimeError, match="Quality gate check failed"):
        apply(**_apply_kwargs(apps_dir, small_profile, db_path=db_file))

    assert list(apps_dir.iterdir()) == [], "no published folder and no .staging-* residue"
    assert not any(child.name.startswith(".staging-") for child in apps_dir.iterdir())

    from worksisyphus.db import get_connection

    conn = get_connection(db_file)
    try:
        assert conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 0
    finally:
        conn.close()


def test_backfill_scores_without_a_profile_on_disk(monkeypatch, tmp_path) -> None:
    """Backfill delivers nothing, so a missing profile.json must degrade, not raise.

    Regression: it resolved profile.json eagerly even when handed an explicit
    applications_dir, so every checkout without the gitignored profile (fresh clone, CI)
    failed here once load_profile stopped falling back to the fixture.
    """
    import worksisyphus.application as app_module
    from worksisyphus.application import backfill_evaluations

    monkeypatch.chdir(tmp_path)
    apps = tmp_path / "applications"
    folder = apps / "2026-08-01_oldco_swe"
    folder.mkdir(parents=True)
    (folder / "meta.json").write_text(json.dumps({"company": "OldCo", "role": "SWE", "status": "applied"}))
    (folder / "jd.txt").write_text("Python backend engineer.")
    (folder / "Simon_Chen_Resume.pdf").write_bytes(b"%PDF-fake")
    monkeypatch.setattr(app_module, "check_pdf_ats", lambda p, **kw: ATSCheckResult(True, (), 1, 400, "Python"))

    messages: list[str] = []
    assert not Path("profile.json").exists()
    scored = backfill_evaluations(applications_dir=apps, log=messages.append)

    assert [name for name, _ in scored] == ["2026-08-01_oldco_swe"]
    assert any("without a candidate name" in m for m in messages), messages


def test_backfill_never_touches_the_profile_when_nothing_needs_scoring(monkeypatch, tmp_path) -> None:
    """The load is deferred until a name is actually needed, not merely deferred in name."""
    import worksisyphus.application as app_module
    from worksisyphus.application import backfill_evaluations

    def exploding_load(_path):
        raise AssertionError("backfill must not resolve the profile when it scores nothing")

    monkeypatch.setattr(app_module, "load_profile", exploding_load)

    apps = tmp_path / "applications"
    folder = apps / "2026-08-01_oldco_swe"
    folder.mkdir(parents=True)
    (folder / "meta.json").write_text(
        json.dumps({"company": "OldCo", "role": "SWE", "status": "applied", "evaluation": {"total_score": 1}})
    )
    (folder / "Simon_Chen_Resume.pdf").write_bytes(b"%PDF-fake")

    assert backfill_evaluations(applications_dir=apps) == []
