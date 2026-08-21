from __future__ import annotations

import json
from datetime import date

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
    res_dir = tmp_path / "resumes"

    folder, _comp_res, ats_res = apply(
        plan_text=plan_text,
        jd_text="Backend engineer role",
        company="Acme Corp",
        role="Product Engineer",
        when=date(2026, 8, 20),
        profile=small_profile,
        applications_dir=apps_dir,
        pdf_dir=res_dir,
        sync_cloud=False,
    )

    assert folder == apps_dir / "2026-08-20_acme-corp_product-engineer"
    assert (folder / "Simon_Chen_Resume.pdf").is_file()
    assert (folder / "plan.json").is_file()
    assert (folder / "jd.txt").read_text() == "Backend engineer role\n"
    assert (res_dir / "Simon_Chen_Resume.pdf").is_file()
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
    res_dir = tmp_path / "resumes"
    with pytest.raises(RuntimeError, match="Quality gate check failed"):
        apply(
            plan_text=json.dumps({"experiences": {"org-a": ["a1"]}}),
            jd_text="Backend engineer role",
            company="Acme Corp",
            role="Product Engineer",
            when=date(2026, 8, 20),
            profile=small_profile,
            applications_dir=apps_dir,
            pdf_dir=res_dir,
            sync_cloud=False,
        )

    # Verify atomic rollback: no folder in applications_dir and no mirrored PDF in res_dir
    assert not (apps_dir / "2026-08-20_acme-corp_product-engineer").exists()
    assert not (res_dir / "Simon_Chen_Resume.pdf").exists()
    # No staging residue is left inside applications/
    assert list(apps_dir.iterdir()) == []


def test_apply_gate_failure_leaves_previous_delivered_resume_intact(small_profile, monkeypatch, tmp_path) -> None:
    """A resume that fails a gate must never replace the resume already staged for delivery."""

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
    res_dir = tmp_path / "resumes"
    res_dir.mkdir(parents=True)
    (res_dir / "Simon_Chen_Resume.pdf").write_bytes(b"%PDF-previously-delivered-good-resume")

    with pytest.raises(RuntimeError, match="Quality gate check failed"):
        apply(
            plan_text=json.dumps({"experiences": {"org-a": ["a1"]}}),
            jd_text="Backend engineer role",
            company="Acme Corp",
            role="Product Engineer",
            when=date(2026, 8, 20),
            profile=small_profile,
            applications_dir=apps_dir,
            pdf_dir=res_dir,
            sync_cloud=False,
        )

    assert (res_dir / "Simon_Chen_Resume.pdf").read_bytes() == b"%PDF-previously-delivered-good-resume"


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
        pdf_dir=tmp_path / "resumes",
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
        pdf_dir=tmp_path / "resumes",
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
            pdf_dir=tmp_path / "resumes",
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
        pdf_dir=tmp_path / "resumes",
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
        pdf_dir=tmp_path / "resumes",
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
        pdf_dir=tmp_path / "resumes",
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
