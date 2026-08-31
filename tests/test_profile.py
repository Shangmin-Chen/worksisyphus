from __future__ import annotations

import json

import pytest

from worksisyphus import load_profile, profile_index


def test_real_profile_loads_expected_shape(real_profile) -> None:
    assert real_profile.contact.name == "Simon Chen"
    assert len(real_profile.experiences) == 3
    assert len(real_profile.projects) == 9
    persephone = real_profile.projects["persephone"]
    assert len(persephone.bullets) == 8
    assert persephone.tech == "Python, Cython/C++17, Rust, Modal, FAISS"
    assert set(real_profile.skills) == {
        "languages",
        "frameworks_and_libraries",
        "databases_and_infrastructure",
    }


def test_entry_ids_match_their_slugs(real_profile) -> None:
    assert all(exp.id == slug for slug, exp in real_profile.experiences.items())
    assert all(proj.id == slug for slug, proj in real_profile.projects.items())


def test_profile_index_lists_slugs_and_bullets(small_profile) -> None:
    index = profile_index(small_profile)
    assert "org-a: Engineer at OrgA (2025)" in index
    assert "  org-b.b2: B two" in index
    assert "proj2:" in index
    assert "languages: Python, Rust" in index


def test_values_stay_verbatim_tex(real_profile) -> None:
    joined = profile_index(real_profile)
    assert r"\$8K" in joined
    assert r"$\sim$20$\mu$s" in joined


def test_missing_profile_raises_instead_of_falling_back(tmp_path, monkeypatch) -> None:
    """A missing profile.json must fail loudly, never silently load another profile.

    Regression: load_profile used to fall back to tests/fixtures/profile.json, whose contact
    block is scrubbed to example.com placeholders. Four resumes were built and sent with a
    dead phone and email while passing every quality gate, because only the header was wrong.
    """
    monkeypatch.chdir(tmp_path)
    fixtures = tmp_path / "tests" / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "profile.json").write_text(
        json.dumps({"contact": {"name": "Simon Chen", "email": "simon@example.com"}}), encoding="utf-8"
    )

    with pytest.raises(FileNotFoundError) as excinfo:
        load_profile()
    assert "db export-profile" in str(excinfo.value)


def test_real_profile_contact_is_not_placeholder(real_profile) -> None:
    """The loaded profile must carry deliverable contact details, not fixture placeholders."""
    contact = real_profile.contact
    if "example.com" in contact.email:
        pytest.skip("running against the scrubbed fixture (no profile.json present)")
    for field_name in ("email", "phone", "website", "github", "linkedin"):
        value = getattr(contact, field_name)
        assert value, f"contact.{field_name} is empty"
        assert "example.com" not in value, f"contact.{field_name} is a placeholder: {value}"
        assert "555-555-5555" not in value, f"contact.{field_name} is a placeholder: {value}"
