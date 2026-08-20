from __future__ import annotations

import hashlib
import json
from datetime import date

import pytest

from worksisyphus import archive_application
from worksisyphus.archive import list_applications, update_application_status


@pytest.fixture()
def built(tmp_path):
    plan = tmp_path / "acme_swe.json"
    plan.write_text('{"projects": ["proj1"]}', encoding="utf-8")
    pdf = tmp_path / "acme_swe_resume.pdf"
    pdf.write_bytes(b"%PDF-fake")
    (tmp_path / ".provenance.json").write_text(
        json.dumps(
            {
                "plan_hash": hashlib.sha256(plan.read_bytes()).hexdigest(),
                "pdf_hash": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return plan, pdf, tmp_path / "applications"


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


def test_archive_rejects_provenance_mismatch(built) -> None:
    plan, pdf, apps = built
    prov = pdf.parent / ".provenance.json"
    prov.write_text(
        json.dumps(
            {
                "plan_hash": "deadbeef1234",
                "pdf_hash": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="provenance mismatch"):
        archive_application(plan, pdf, "jd", company="Acme", applications_dir=apps)


@pytest.mark.parametrize("contents", ["{", "[]", "{}"])
def test_archive_rejects_invalid_provenance(built, contents: str) -> None:
    plan, pdf, apps = built
    (pdf.parent / ".provenance.json").write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match="Could not validate build provenance"):
        archive_application(plan, pdf, "jd", company="Acme", applications_dir=apps)


def test_archive_rejects_missing_provenance(built) -> None:
    plan, pdf, apps = built
    (pdf.parent / ".provenance.json").unlink()
    with pytest.raises(ValueError, match="No build provenance"):
        archive_application(plan, pdf, "jd", company="Acme", applications_dir=apps)


def test_archive_rejects_pdf_changed_after_tailoring(built) -> None:
    plan, pdf, apps = built
    pdf.write_bytes(b"%PDF-replaced")
    with pytest.raises(ValueError, match="changed after tailoring"):
        archive_application(plan, pdf, "jd", company="Acme", applications_dir=apps)


def test_archive_accepts_crlf_plan_and_preserves_original_bytes(built) -> None:
    plan, pdf, apps = built
    plan_bytes = b'{\r\n  "projects": ["proj1"]\r\n}\r\n'
    plan.write_bytes(plan_bytes)
    normalized_plan = plan_bytes.decode("utf-8").replace("\r\n", "\n")
    (pdf.parent / ".provenance.json").write_text(
        json.dumps(
            {
                "plan_hash": hashlib.sha256(normalized_plan.encode("utf-8")).hexdigest(),
                "pdf_hash": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )

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

    target, old, new = update_application_status("acme_swe", "phone_screen", applications_dir=apps)
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
        update_application_status("acme_swe", "phone_screen", applications_dir=apps)
    with pytest.raises(FileNotFoundError, match="No application folder"):
        update_application_status("acme", "phone_screen", applications_dir=apps)
    with pytest.raises(ValueError, match="must not be empty"):
        update_application_status("", "phone_screen", applications_dir=apps)

    target, old, new = update_application_status(first.name, "phone_screen", applications_dir=apps)
    assert (target, old, new) == (first, "applied", "phone_screen")
    assert not (first / "meta.json.tmp").exists()
    assert json.loads((second / "meta.json").read_text(encoding="utf-8"))["status"] == "applied"


def test_list_applications_reports_invalid_metadata(tmp_path) -> None:
    folder = tmp_path / "applications" / "2026-07-11_acme_swe"
    folder.mkdir(parents=True)
    (folder / "meta.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match=r"2026-07-11_acme_swe.*JSON object"):
        list_applications(tmp_path / "applications")


def test_archive_releases_tailor_lock(built) -> None:
    plan, pdf, apps = built
    lock_path = pdf.parent / ".tailor.lock"
    lock_path.write_text('{"plan_name": "acme_swe"}', encoding="utf-8")
    assert lock_path.is_file()

    archive_application(plan, pdf, "the JD text", company="Acme", applications_dir=apps)
    assert not lock_path.exists()
