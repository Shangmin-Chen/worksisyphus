from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from worksisyphus import CompileResult, apply, archive_application
from worksisyphus.application import list_applications, slugify, update_application_status
from worksisyphus.ats import ATSCheckResult


@pytest.fixture()
def built(tmp_path):
    plan = tmp_path / "acme_swe.json"
    plan.write_text('{"projects": ["proj1"]}', encoding="utf-8")
    pdf = tmp_path / "acme_swe_resume.pdf"
    pdf.write_bytes(b"%PDF-fake")
    return plan, pdf, tmp_path / "applications"


def test_slugify() -> None:
    assert slugify("Primitive") == "primitive"
    assert slugify("Product Engineer") == "product-engineer"
    assert slugify("  Founding SWE (AI / Systems)  ") == "founding-swe-ai-systems"


def test_apply_compiles_freezes_and_validates(small_profile, monkeypatch, tmp_path) -> None:
    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        pdf_path = pdf_dir / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)

    def fake_ats(pdf_path, **kwargs) -> ATSCheckResult:
        return ATSCheckResult(passed=True, problems=(), pages=1, word_count=450, text="Simon Chen")

    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", fake_compile)
    monkeypatch.setattr(pipe_module, "load_profile", lambda _path: small_profile)
    monkeypatch.setattr(app_module, "check_pdf_ats", fake_ats)

    plan_text = json.dumps({"experiences": {"org-a": ["a1"]}, "projects": {"proj1": ["p1"]}})
    apps_dir = tmp_path / "applications"
    res_dir = tmp_path / "resumes"

    folder, comp_res, ats_res = apply(
        plan_text=plan_text,
        jd_text="Backend engineer role",
        company="Acme Corp",
        role="Product Engineer",
        when=date(2026, 8, 20),
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


def test_apply_rejects_empty_jd(tmp_path) -> None:
    with pytest.raises(ValueError, match="jd_text is empty"):
        apply(
            plan_text="{}",
            jd_text="   ",
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
    monkeypatch.setattr(pipe_module, "load_profile", lambda _path: small_profile)
    monkeypatch.setattr(
        app_module, "check_pdf_ats", lambda p, **kw: ATSCheckResult(True, (), 1, 100, "text")
    )

    plan_text = json.dumps({"experiences": {"org-a": ["a1"]}})
    apps_dir = tmp_path / "applications"

    apply(
        plan_text=plan_text,
        jd_text="JD text",
        company="Acme",
        role="SWE",
        when=date(2026, 8, 20),
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
            applications_dir=apps_dir,
            pdf_dir=tmp_path / "resumes",
            sync_cloud=False,
        )


def test_archive_freezes_all_four_files(built) -> None:
    plan, pdf, apps = built
    folder = archive_application(
        plan,
        pdf,
        "the JD text",
        company="Acme",
        role="SWE",
        source_url="https://acme.jobs/1",
        when=date(2026, 7, 11),
        applications_dir=apps,
    )
    assert folder == apps / "2026-07-11_acme_swe"
    assert (folder / "plan.json").read_text() == plan.read_text()
    assert (folder / "Simon_Chen_Resume.pdf").read_bytes() == b"%PDF-fake"
    assert (folder / "jd.txt").read_text() == "the JD text\n"
    meta = json.loads((folder / "meta.json").read_text())
    assert meta == {
        "company": "Acme",
        "role": "SWE",
        "date": "2026-07-11",
        "source_url": "https://acme.jobs/1",
        "status": "applied",
    }


def test_archive_rejects_empty_jd(built) -> None:
    plan, pdf, apps = built
    with pytest.raises(ValueError, match="jd_text is empty"):
        archive_application(plan, pdf, "  ", company="Acme", when=date(2026, 7, 11), applications_dir=apps)


def test_archive_is_immutable(built) -> None:
    plan, pdf, apps = built
    archive_application(plan, pdf, "jd", company="Acme", when=date(2026, 7, 11), applications_dir=apps)
    with pytest.raises(FileExistsError, match="immutable"):
        archive_application(plan, pdf, "jd", company="Acme", when=date(2026, 7, 11), applications_dir=apps)


def test_archive_requires_compiled_pdf(built) -> None:
    plan, pdf, apps = built
    pdf.unlink()
    with pytest.raises(FileNotFoundError, match="tailor"):
        archive_application(plan, pdf, "jd", company="Acme", applications_dir=apps)


def test_archive_accepts_crlf_plan_and_preserves_original_bytes(built) -> None:
    plan, pdf, apps = built
    plan_bytes = b'{\r\n  "projects": ["proj1"]\r\n}\r\n'
    plan.write_bytes(plan_bytes)

    folder = archive_application(plan, pdf, "jd", company="Acme", applications_dir=apps)
    assert (folder / "plan.json").read_bytes() == plan_bytes


def test_list_and_update_application_status(built) -> None:
    plan, pdf, apps = built
    folder = archive_application(
        plan, pdf, "jd text", company="Acme", role="SWE", when=date(2026, 7, 11), applications_dir=apps
    )
    app_list = list_applications(applications_dir=apps)
    assert len(app_list) == 1
    assert app_list[0]["company"] == "Acme"
    assert app_list[0]["status"] == "applied"

    target, old, new = update_application_status("acme_swe", "phone_screen", applications_dir=apps, sync_cloud=False)
    assert target == folder
    assert old == "applied"
    assert new == "phone_screen"

    updated_meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    assert updated_meta["status"] == "phone_screen"


def test_update_status_rejects_ambiguous_stem_and_partial_match(built) -> None:
    plan, pdf, apps = built
    first = archive_application(plan, pdf, "jd", company="Acme", when=date(2026, 7, 11), applications_dir=apps)
    second = archive_application(plan, pdf, "jd", company="Acme", when=date(2026, 7, 12), applications_dir=apps)

    with pytest.raises(ValueError, match="ambiguous"):
        update_application_status("acme_swe", "phone_screen", applications_dir=apps, sync_cloud=False)
    with pytest.raises(FileNotFoundError, match="No application folder"):
        update_application_status("acme", "phone_screen", applications_dir=apps, sync_cloud=False)
    with pytest.raises(ValueError, match="must not be empty"):
        update_application_status("", "phone_screen", applications_dir=apps, sync_cloud=False)

    target, old, new = update_application_status(first.name, "phone_screen", applications_dir=apps, sync_cloud=False)
    assert (target, old, new) == (first, "applied", "phone_screen")
    assert not (first / "meta.json.tmp").exists()
    assert json.loads((second / "meta.json").read_text(encoding="utf-8"))["status"] == "applied"


def test_list_applications_reports_invalid_metadata(tmp_path) -> None:
    folder = tmp_path / "applications" / "2026-07-11_acme_swe"
    folder.mkdir(parents=True)
    (folder / "meta.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match=r"2026-07-11_acme_swe.*JSON object"):
        list_applications(tmp_path / "applications")
