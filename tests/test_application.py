from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from worksisyphus import CompileResult, apply
from worksisyphus.application import (
    list_applications,
    parse_app_folder,
    resolve_application_folder,
    slugify,
    update_application_status,
)
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


def _fake_compile_factory():
    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        pdf_path = pdf_dir / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)

    return fake_compile


def _patch_apply_pipeline(monkeypatch) -> None:
    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    monkeypatch.setattr(pipe_module, "compile_tex", _fake_compile_factory())
    monkeypatch.setattr(
        app_module,
        "run_resume_gates",
        lambda *a, **kw: ((GateResult("ATS", True, ()),), ATSCheckResult(True, (), 1, 100, "text")),
    )


def test_apply_same_day_second_attempt_allocates_suffix(small_profile, monkeypatch, tmp_path) -> None:
    _patch_apply_pipeline(monkeypatch)

    plan_text = json.dumps({"experiences": {"org-a": ["a1"]}})
    apps_dir = tmp_path / "applications"
    kwargs = dict(
        plan_text=plan_text,
        jd_text="JD text",
        company="Acme",
        role="SWE",
        when=date(2026, 8, 20),
        profile=small_profile,
        applications_dir=apps_dir,
        sync_cloud=False,
    )

    first, _, _ = apply(**kwargs)
    second, _, _ = apply(**kwargs)
    third, _, _ = apply(**kwargs)

    assert [folder.name for folder in (first, second, third)] == [
        "2026-08-20_acme_swe",
        "2026-08-20_acme_swe_2",
        "2026-08-20_acme_swe_3",
    ]
    for folder in (first, second, third):
        assert (folder / "meta.json").is_file()
        assert json.loads((folder / "meta.json").read_text(encoding="utf-8"))["status"] == "applied"


def test_apply_never_mutates_a_published_folder(small_profile, monkeypatch, tmp_path) -> None:
    _patch_apply_pipeline(monkeypatch)

    plan_text = json.dumps({"experiences": {"org-a": ["a1"]}})
    apps_dir = tmp_path / "applications"

    first, _, _ = apply(
        plan_text=plan_text,
        jd_text="JD text",
        company="Acme",
        role="SWE",
        when=date(2026, 8, 20),
        profile=small_profile,
        applications_dir=apps_dir,
        sync_cloud=False,
    )
    before = {path.name: path.read_bytes() for path in sorted(first.iterdir())}

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

    after = {path.name: path.read_bytes() for path in sorted(first.iterdir())}
    assert before == after


def test_apply_retries_next_suffix_when_target_claimed_concurrently(small_profile, monkeypatch, tmp_path) -> None:
    import errno as errno_module

    import worksisyphus.application as app_module

    _patch_apply_pipeline(monkeypatch)
    apps_dir = tmp_path / "applications"

    # Simulate a concurrent apply claiming ..._swe_2 between allocation and publish.
    original_allocate = app_module._allocate_target
    real_replace = app_module.os.replace
    occupied = apps_dir / "2026-08-20_acme_swe_2"
    allocations = {"n": 0}

    def racy_allocate(applications_dir, base_target):
        target = original_allocate(applications_dir, base_target)
        allocations["n"] += 1
        if allocations["n"] == 2 and target == occupied and not occupied.exists():
            occupied.mkdir(parents=True)
            (occupied / "meta.json").write_text("{}", encoding="utf-8")
        return target

    def replace(src, dst):
        if Path(dst) == occupied and occupied.exists():
            raise OSError(errno_module.ENOTEMPTY, "Directory not empty")
        return real_replace(src, dst)

    monkeypatch.setattr(app_module, "_allocate_target", racy_allocate)
    monkeypatch.setattr(app_module.os, "replace", replace)

    common = dict(
        plan_text=json.dumps({"experiences": {"org-a": ["a1"]}}),
        jd_text="JD text",
        company="Acme",
        role="SWE",
        when=date(2026, 8, 20),
        profile=small_profile,
        applications_dir=apps_dir,
        sync_cloud=False,
    )
    apply(**common)  # claims the plain slot
    folder, _, _ = apply(**common)
    assert folder.name == "2026-08-20_acme_swe_3"


def test_apply_uses_private_tex_directory(small_profile, monkeypatch, tmp_path) -> None:
    seen_tex_dirs: list[Path] = []

    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        seen_tex_dirs.append(Path(tex_dir))
        pdf_path = Path(pdf_dir) / f"{name}.pdf"
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
    apply(
        plan_text=json.dumps({"experiences": {"org-a": ["a1"]}}),
        jd_text="jd",
        company="Acme",
        role="SWE",
        when=date(2026, 7, 11),
        profile=small_profile,
        applications_dir=apps_dir,
        sync_cloud=False,
    )

    assert len(seen_tex_dirs) == 1
    build_dir = seen_tex_dirs[0]
    assert build_dir.name.startswith(app_module.TEX_BUILD_PREFIX)
    assert Path(build_dir).anchor != "" and "tex_files" not in build_dir.parts
    assert not build_dir.exists()  # cleaned up after the run


def test_slugify_never_emits_underscore_separator() -> None:
    for raw in ("SWE 2", "SDE_2", "Acme Corp.", "23andMe", "C++ Developer"):
        assert "_" not in slugify(raw), raw


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


def test_parse_app_folder_handles_legacy_names() -> None:
    # Legacy pre-#34 stems with literal underscores and hyphen-digits are never ordinals.
    assert parse_app_folder("2026-07-09_bosch_software_engineer_ii") == (
        "2026-07-09",
        "bosch_software_engineer_ii",
        None,
    )
    assert parse_app_folder("2026-08-18_bloomberg_software-engineer-2027") == (
        "2026-08-18",
        "bloomberg_software-engineer-2027",
        None,
    )


def test_parse_app_folder_ordinal_requires_the_base_sibling() -> None:
    siblings = ["2026-08-24_google_swe", "2026-08-24_google_swe_2", "2026-08-24_google_swe_10"]
    assert parse_app_folder("2026-08-24_google_swe_2", siblings) == ("2026-08-24", "google_swe", 2)
    assert parse_app_folder("2026-08-24_google_swe_10", siblings) == ("2026-08-24", "google_swe", 10)
    # Without its base on disk the tail stays literal; no lineage is invented.
    assert parse_app_folder("2027-01-01_x_y_2") == ("2027-01-01", "x_y_2", None)


def test_parse_app_folder_requires_a_date_prefix() -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_app_folder("not-a-date")


def test_resolve_lists_each_ambiguous_match_on_its_own_line(tmp_path) -> None:
    for day in ("02", "08"):
        folder = tmp_path / "applications" / f"2026-08-{day}_google_data-engineer"
        folder.mkdir(parents=True)
        (folder / "meta.json").write_text(json.dumps({"company": "Google", "status": "applied"}), encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        resolve_application_folder("google_data-engineer", applications_dir=tmp_path / "applications")
    lines = excinfo.value.args[0].splitlines()
    assert any("2026-08-02_google_data-engineer" in line for line in lines)
    assert any("2026-08-08_google_data-engineer" in line for line in lines)


def test_list_applications_orders_newest_first_then_retry_order(tmp_path) -> None:
    apps_dir = tmp_path / "applications"
    for name in (
        "2026-08-20_acme_swe",
        "2026-08-24_google_swe_2",
        "2026-08-24_google_swe",
        "2026-08-24_google_swe_10",
    ):
        folder = apps_dir / name
        folder.mkdir(parents=True)
        (folder / "meta.json").write_text(json.dumps({"company": "Co", "status": "applied"}), encoding="utf-8")

    order = [app["folder"] for app in list_applications(applications_dir=apps_dir)]
    assert order == [
        "2026-08-24_google_swe",
        "2026-08-24_google_swe_2",
        "2026-08-24_google_swe_10",
        "2026-08-20_acme_swe",
    ]
