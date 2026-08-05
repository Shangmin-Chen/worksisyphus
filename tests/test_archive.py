from __future__ import annotations

import json
from datetime import date

import pytest

from worksisyphus import archive_application


@pytest.fixture()
def built(tmp_path):
    plan = tmp_path / "acme_swe.json"
    plan.write_text('{"projects": ["proj1"]}', encoding="utf-8")
    pdf = tmp_path / "acme_swe_resume.pdf"
    pdf.write_bytes(b"%PDF-fake")
    return plan, pdf, tmp_path / "applications"


def test_archive_freezes_all_four_files(built) -> None:
    plan, pdf, apps = built
    folder = archive_application(plan, pdf, "the JD text", company="Acme", role="SWE",
                                 source_url="https://acme.jobs/1", when=date(2026, 7, 11), applications_dir=apps)
    assert folder == apps / "2026-07-11_acme_swe"
    assert (folder / "plan.json").read_text() == plan.read_text()
    assert (folder / "Simon_Chen_Resume.pdf").read_bytes() == b"%PDF-fake"
    assert (folder / "jd.txt").read_text() == "the JD text\n"
    meta = json.loads((folder / "meta.json").read_text())
    assert meta == {"company": "Acme", "role": "SWE", "date": "2026-07-11",
                    "source_url": "https://acme.jobs/1", "status": "applied"}


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
