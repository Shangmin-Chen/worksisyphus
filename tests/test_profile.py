from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from worksisyphus import load_profile, profile_index, validate_contact
from worksisyphus.profile import Contact


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


GOOD_CONTACT = Contact(
    name="Simon Chen",
    email="simon.chen@fixture.test",
    phone="617-201-4477",
    website="https://simonchen.dev",
    github="https://github.com/Shangmin-Chen",
    linkedin="https://linkedin.com/in/shangmin-chen",
)


def test_validate_contact_accepts_a_deliverable_contact() -> None:
    validate_contact(GOOD_CONTACT)


def test_validate_contact_accepts_missing_optional_links() -> None:
    """website/github/linkedin are optional: a resume without a portfolio link still reaches a human."""
    validate_contact(Contact(name="Simon Chen", email="simon.chen@fixture.test", phone="617-201-4477"))


@pytest.mark.parametrize("field_name", ["name", "email", "phone"])
def test_validate_contact_rejects_empty_required_fields(field_name) -> None:
    contact = dataclasses.replace(GOOD_CONTACT, **{field_name: "   "})
    with pytest.raises(ValueError) as excinfo:
        validate_contact(contact)
    message = str(excinfo.value)
    assert f"contact.{field_name}" in message
    assert "db export-profile" in message


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("email", "simon@example.com"),
        ("email", "simon@example.org"),
        ("email", "simon@example.dev"),
        ("phone", "555-555-5555"),
        ("phone", "555-0100"),
        ("phone", "(617) 555-0199"),
        ("website", "https://example.com"),
        ("github", "https://github.com/example"),
        ("linkedin", "https://linkedin.com/in/example"),
    ],
)
def test_validate_contact_rejects_placeholders(field_name, value) -> None:
    """Optional fields are checked too: a placeholder link is still a wrong link on a sent resume."""
    contact = dataclasses.replace(GOOD_CONTACT, **{field_name: value})
    with pytest.raises(ValueError) as excinfo:
        validate_contact(contact)
    message = str(excinfo.value)
    assert f"contact.{field_name}" in message
    assert value in message, "the error must name the offending value, not just the field"


def test_validate_contact_rejects_the_test_fixture_profile() -> None:
    """The exact profile that shipped four dead resumes must not survive validation."""
    fixture = Path(__file__).resolve().parent / "fixtures" / "profile.json"
    with pytest.raises(ValueError, match="placeholder"):
        validate_contact(load_profile(fixture).contact, source=str(fixture))


@pytest.mark.parametrize(
    ("phone", "is_placeholder"),
    [
        # Compact NANP forms the old \b-anchored regex missed: \b needs a non-word character
        # before the 555, so a number written without separators sailed through. Both of these
        # are 347-555-0100 -- reserved-fictional, exactly what the check claims to catch.
        ("3475550100", True),
        ("+13475550100", True),
        # Already caught before this fix; it must stay caught.
        ("347 5550100", True),
        # Real numbers that contain the digits 555 once separators are stripped (2129555187,
        # 02075550123, 442075550123). A false positive here blocks a legitimate resume build,
        # which is worse than the false negative above, so these must stay accepted.
        ("212-955-5187", False),
        ("020 7555 0123", False),
        ("+44 20 7555 0123", False),
    ],
)
def test_placeholder_phone_verdicts(phone, is_placeholder) -> None:
    """The 555 exchange is fictional wherever it sits; the digits 555 elsewhere are not."""
    contact = dataclasses.replace(GOOD_CONTACT, phone=phone)
    if is_placeholder:
        with pytest.raises(ValueError) as excinfo:
            validate_contact(contact)
        assert "555 exchange" in str(excinfo.value)
    else:
        validate_contact(contact)
