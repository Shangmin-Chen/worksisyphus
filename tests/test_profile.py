from __future__ import annotations

import dataclasses
import json

import pytest

from worksisyphus import load_profile, profile_index, validate_contact
from worksisyphus.profile import REQUIRED_CONTACT_FIELDS, Contact

GATED_REAL_SLUGS = frozenset(
    {
        "persephone",
        "fitness-tracker",
        "spark-food-waste",
        "ml-marketplace",
        "personal-website",
        "bu-engineering-it",
    }
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


def test_required_contact_fields_are_real_contact_attributes() -> None:
    """A renamed Contact field must break here, loudly, not degrade validate_contact into
    a confusing unconditional failure via getattr's silent default."""
    assert set(REQUIRED_CONTACT_FIELDS) <= {f.name for f in dataclasses.fields(Contact)}


def test_fixture_skill_groups_exist_in_the_real_profile(small_profile, real_profile) -> None:
    assert set(small_profile.skills) <= set(real_profile.skills)


def test_fixture_slugs_do_not_collide_with_guarded_real_slugs(small_profile, real_profile) -> None:
    fixture_slugs = set(small_profile.experiences) | set(small_profile.projects)
    real_slugs = set(real_profile.experiences) | set(real_profile.projects)
    assert fixture_slugs.isdisjoint(GATED_REAL_SLUGS)
    assert fixture_slugs.isdisjoint(real_slugs)


def test_load_profile_names_the_offending_experience(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "contact": {"name": "Simon Chen", "email": "simon@example.com", "phone": "617-000-0000"},
                "experiences": {
                    "acme-co": {
                        "role": "Engineer",
                        "org": "Acme Co",
                        "location": "NY",
                        "date": "2025",
                        "bullets": {},
                        "tech_stack": "x",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        load_profile(profile_path)
    message = str(excinfo.value)
    assert "acme-co" in message
    assert str(profile_path) in message


def test_load_profile_names_the_offending_project(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "contact": {"name": "Simon Chen", "email": "simon@example.com", "phone": "617-000-0000"},
                "projects": {
                    "widget": {
                        "name": "Widget",
                        "tech": "Python",
                        "date": "2025",
                        "bullets": {},
                        "tech_stack": "x",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        load_profile(profile_path)
    message = str(excinfo.value)
    assert "widget" in message
    assert str(profile_path) in message


def test_load_profile_dict_key_slug_overrides_inner_id(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "contact": {"name": "Simon Chen", "email": "simon@example.com", "phone": "617-000-0000"},
                "experiences": {
                    "acme-co": {
                        "id": "wrong-slug",
                        "role": "Engineer",
                        "org": "Acme Co",
                        "location": "NY",
                        "date": "2025",
                        "bullets": {},
                    }
                },
                "projects": {
                    "widget": {
                        "id": "also-wrong",
                        "name": "Widget",
                        "tech": "Python",
                        "date": "2025",
                        "bullets": {},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    profile = load_profile(profile_path)
    assert profile.experiences["acme-co"].id == "acme-co"
    assert profile.projects["widget"].id == "widget"


def test_load_profile_names_the_offending_education_entry(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "contact": {"name": "Simon Chen", "email": "simon@example.com", "phone": "617-000-0000"},
                "education": [
                    {
                        "institution": "Example University",
                        "location": "Boston, MA",
                        "degre": "B.S. Computer Science",
                        "date": "2026",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        load_profile(profile_path)
    message = str(excinfo.value)
    assert str(profile_path) in message
    assert "education entry 0" in message
    assert "Example University" in message


def test_load_profile_names_a_bad_contact_key(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "contact": {
                    "name": "Simon Chen",
                    "email": "simon@example.com",
                    "phone": "617-000-0000",
                    "fax": "555-1234",
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        load_profile(profile_path)
    assert str(profile_path) in str(excinfo.value)


@pytest.mark.parametrize(
    ("section", "payload", "needle"),
    [
        ("education", {"education": [None]}, "education entry 0"),
        ("experiences", {"experiences": {"acme-co": None}}, "experience 'acme-co'"),
        ("projects", {"projects": {"widget": "not-a-dict"}}, "project 'widget'"),
    ],
)
def test_load_profile_rejects_non_dict_entries(tmp_path, section, payload, needle) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "contact": {"name": "Simon Chen", "email": "simon@example.com", "phone": "617-000-0000"},
                **payload,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        load_profile(profile_path)
    message = str(excinfo.value)
    assert str(profile_path) in message
    assert needle in message


@pytest.mark.parametrize(
    ("payload", "needle"),
    [
        ({"education": None}, "education section"),
        ({"experiences": None}, "experiences section"),
        ({"projects": None}, "projects section"),
        ({"skills": None}, "skills section"),
        ({"skills": {"languages": None}}, "skills.languages"),
    ],
)
def test_load_profile_rejects_invalid_sections(tmp_path, payload, needle) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "contact": {"name": "Simon Chen", "email": "simon@example.com", "phone": "617-000-0000"},
                **payload,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        load_profile(profile_path)
    message = str(excinfo.value)
    assert str(profile_path) in message
    assert needle in message


def test_load_profile_rejects_null_coursework(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "contact": {"name": "Simon Chen", "email": "simon@example.com", "phone": "617-000-0000"},
                "education": [
                    {
                        "institution": "Example University",
                        "location": "Boston, MA",
                        "degree": "B.S. Computer Science",
                        "date": "2026",
                        "coursework": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        load_profile(profile_path)
    message = str(excinfo.value)
    assert str(profile_path) in message
    assert "coursework" in message
    assert "education entry 0" in message
    assert "Example University" in message


def test_load_profile_strips_a_leading_bom(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    payload = json.dumps({"contact": {"name": "Simon Chen", "email": "s@example.com", "phone": "617-000-0000"}})
    profile_path.write_text("﻿" + payload, encoding="utf-8")
    profile = load_profile(profile_path)
    assert profile.contact.name == "Simon Chen"
