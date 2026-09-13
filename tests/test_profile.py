from __future__ import annotations

import dataclasses
import json

import pytest

from worksisyphus import load_profile, profile_index, validate_contact
from worksisyphus.profile import (
    Contact,
    Education,
    Experience,
    Project,
    profile_content_differences,
    profile_drift_summary,
)


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
    """A missing profile.json must fail loudly, never silently load another profile."""
    monkeypatch.chdir(tmp_path)
    fixtures = tmp_path / "tests" / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "profile.json").write_text(
        json.dumps({"contact": {"name": "Simon Chen", "email": "simon@example.com"}}), encoding="utf-8"
    )

    with pytest.raises(FileNotFoundError) as excinfo:
        load_profile()
    assert "db export-profile" in str(excinfo.value)


VALID_CONTACT = Contact(
    name="Simon Chen",
    email="simon.chen@fixture.test",
    phone="617-201-4477",
    website="https://simonchen.dev",
    github="https://github.com/Shangmin-Chen",
    linkedin="https://linkedin.com/in/shangmin-chen",
)


def test_validate_contact_accepts_valid_contact() -> None:
    validate_contact(VALID_CONTACT)


def test_validate_contact_accepts_missing_optional_links() -> None:
    """website/github/linkedin are optional."""
    validate_contact(Contact(name="Simon Chen", email="simon.chen@fixture.test", phone="617-201-4477"))


@pytest.mark.parametrize("field_name", ["name", "email", "phone"])
def test_validate_contact_rejects_empty_required_fields(field_name) -> None:
    contact = dataclasses.replace(VALID_CONTACT, **{field_name: "   "})
    with pytest.raises(ValueError) as excinfo:
        validate_contact(contact)
    assert f"contact.{field_name} is empty" in str(excinfo.value)


def test_profile_content_differences_reports_missing_experience(small_profile) -> None:
    db_profile = dataclasses.replace(
        small_profile,
        experiences={
            **small_profile.experiences,
            "org-extra": Experience(
                "org-extra",
                "Lead",
                "Extra Org",
                "Remote",
                "2026",
                {"x1": "Extra bullet"},
            ),
        },
    )

    differences = profile_content_differences(small_profile, db_profile)

    assert any("profile has 2 experiences, database has 3" in diff for diff in differences)
    assert any("'org-extra' missing from profile" in diff for diff in differences)


def test_profile_content_differences_reports_truncated_project_bullets(small_profile) -> None:
    truncated_proj1 = Project(
        "proj1",
        "Proj1",
        "Python",
        "2025",
        {"p1": "P1 one"},
    )
    profile = dataclasses.replace(
        small_profile,
        projects={**small_profile.projects, "proj1": truncated_proj1},
    )

    differences = profile_content_differences(profile, small_profile)

    assert any("project 'proj1' has 1 bullets in profile, 3 in database" in diff for diff in differences)
    assert any("'p2'" in diff and "'p3'" in diff for diff in differences)


def test_profile_content_differences_reports_shared_bullet_text_change(small_profile) -> None:
    profile_exp = dataclasses.replace(
        small_profile.experiences["org-a"],
        bullets={**small_profile.experiences["org-a"].bullets, "a1": "Rewritten bullet"},
    )
    profile = dataclasses.replace(
        small_profile,
        experiences={**small_profile.experiences, "org-a": profile_exp},
    )

    differences = profile_content_differences(profile, small_profile)

    assert any(
        "experience 'org-a'.'a1' text: profile has 'Rewritten bullet', database has 'A one'" in diff
        for diff in differences
    )


def test_profile_content_differences_reports_education_degree_change(small_profile) -> None:
    db_profile = dataclasses.replace(
        small_profile,
        education=(Education("BU", "Boston, MA", "B.S. Underwater Basket Weaving", "2026", ("Systems",)),),
    )

    differences = profile_content_differences(small_profile, db_profile)

    assert any(
        "education 'BU' ('2026') degree: profile has 'BA CS', database has 'B.S. Underwater Basket Weaving'" in diff
        for diff in differences
    )


def test_profile_content_differences_reports_education_reorder_without_field_corruption(small_profile) -> None:
    profile = dataclasses.replace(
        small_profile,
        education=(
            Education("MIT", "Cambridge, MA", "M.S. CS", "2028", ("ML",)),
            Education("BU", "Boston, MA", "BA CS", "2026", ("Systems",)),
        ),
    )
    db_profile = dataclasses.replace(
        small_profile,
        education=(
            Education("BU", "Boston, MA", "BA CS", "2026", ("Systems",)),
            Education("MIT", "Cambridge, MA", "M.S. CS", "2028", ("ML",)),
        ),
    )

    differences = profile_content_differences(profile, db_profile)

    assert any("education records are in a different order" in diff for diff in differences)
    assert not any("institution:" in diff for diff in differences)
    assert not any("degree:" in diff for diff in differences)


def test_profile_content_differences_reports_education_field_change_with_stable_keys(small_profile) -> None:
    profile = dataclasses.replace(
        small_profile,
        education=(
            Education("MIT", "Cambridge, MA", "M.S. CS", "2028", ("ML",)),
            Education("BU", "Boston, MA", "BA CS", "2026", ("Systems",)),
        ),
    )
    db_profile = dataclasses.replace(
        small_profile,
        education=(
            Education("BU", "Boston, MA", "BA CS", "2026", ("Systems",)),
            Education("MIT", "Cambridge, MA", "M.Eng. CS", "2028", ("ML",)),
        ),
    )

    differences = profile_content_differences(profile, db_profile)

    assert any("education records are in a different order" in diff for diff in differences)
    assert any(
        "education 'MIT' ('2028') degree: profile has 'M.S. CS', database has 'M.Eng. CS'" in diff
        for diff in differences
    )
    assert not any("'BU' ('2026') degree:" in diff for diff in differences)


def test_profile_drift_summary_prefers_bullet_delta(small_profile) -> None:
    truncated_proj1 = Project(
        "proj1",
        "Proj1",
        "Python",
        "2025",
        {"p1": "P1 one"},
    )
    profile = dataclasses.replace(
        small_profile,
        projects={**small_profile.projects, "proj1": truncated_proj1},
    )

    assert profile_drift_summary(profile, small_profile) == "profile.json is 2 bullets behind the database"


def test_profile_content_differences_reports_extra_bullet_slug_in_profile(small_profile) -> None:
    profile_exp = dataclasses.replace(
        small_profile.experiences["org-a"],
        bullets={**small_profile.experiences["org-a"].bullets, "a-extra": "Extra bullet in profile only"},
    )
    profile = dataclasses.replace(
        small_profile,
        experiences={**small_profile.experiences, "org-a": profile_exp},
    )

    differences = profile_content_differences(profile, small_profile)

    assert any("experience 'org-a' has 4 bullets in profile, 3 in database" in diff for diff in differences)
    assert any("'a-extra' missing from database" in diff for diff in differences)


def test_profile_content_differences_reports_skill_group_item_change(small_profile) -> None:
    db_profile = dataclasses.replace(
        small_profile,
        skills={**small_profile.skills, "languages": ("Python", "Go")},
    )

    differences = profile_content_differences(small_profile, db_profile)

    assert any(
        "skill group 'languages' items: profile has ('Python', 'Rust'), database has ('Python', 'Go')" in diff
        for diff in differences
    )


def test_profile_drift_summary_falls_back_to_first_named_difference(small_profile) -> None:
    db_profile = dataclasses.replace(
        small_profile,
        education=(Education("BU", "Boston, MA", "B.S. Underwater Basket Weaving", "2026", ("Systems",)),),
    )

    assert (
        profile_drift_summary(small_profile, db_profile)
        == "education 'BU' ('2026') degree: profile has 'BA CS', database has 'B.S. Underwater Basket Weaving'"
    )
