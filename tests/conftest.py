from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus import Profile, load_profile, validate_contact  # noqa: E402
from worksisyphus.profile import Contact, Education, Experience, Project  # noqa: E402


@pytest.fixture(scope="session")
def real_profile() -> Profile:
    profile_path = ROOT / "profile.json"
    if not profile_path.is_file():
        profile_path = ROOT / "tests" / "fixtures" / "profile.json"
    return load_profile(profile_path)


@pytest.fixture(scope="session")
def renderable_profile(real_profile) -> Profile:
    """A full-size profile that render_resume will actually accept.

    render_resume now validates the contact block -- no code path may render a placeholder
    header -- and real_profile falls back to tests/fixtures/profile.json, whose contact block
    is deliberately scrubbed. Swapping in a deliverable contact keeps the render-shape tests
    (sections, preamble, verbatim TeX) meaningful on a checkout without profile.json, which is
    every fresh clone and CI. The scrubbed block is still exercised, on purpose, by the tests
    that assert rendering it is impossible.
    """
    try:
        validate_contact(real_profile.contact)
    except ValueError:
        return dataclasses.replace(
            real_profile,
            contact=Contact(
                name="Simon Chen",
                email="simon.chen@fixture.test",
                phone="617-201-4477",
                website="https://simonchen.dev",
                github="https://github.com/fixture-user",
                linkedin="https://linkedin.com/in/fixture-user",
            ),
        )
    return real_profile


@pytest.fixture(scope="session")
def delivered_pdf() -> Path:
    """The newest delivered resume.

    applications/ is the only place a delivered PDF exists, and it is gitignored, so CI has
    none and every test depending on a real PDF skips there.
    """
    apps = ROOT / "applications"
    if apps.is_dir():
        for folder in sorted((d for d in apps.iterdir() if d.is_dir()), reverse=True):
            pdf = folder / "Simon_Chen_Resume.pdf"
            if pdf.is_file():
                return pdf
    pytest.skip("no delivered resume in applications/ (gitignored)")


@pytest.fixture(scope="session")
def canonical_pdf() -> Path:
    """The 3-page canonical view: regenerable build output, not a delivered resume."""
    pdf = ROOT / "tex_files" / "Simon_Chen_Resume_Compiled.pdf"
    if not pdf.is_file():
        pytest.skip("canonical not built; run `uv run worksisyphus compile`")
    return pdf


@pytest.fixture(scope="session")
def deliverable_contact(real_profile) -> Contact:
    """The real, deliverable contact block -- or a skip.

    Tests used to blank email/phone when profile.json was absent, which made the contact
    check vacuous and kept them green against a placeholder header. That is the same bug
    require_contact closes in ats.py: a check that cannot run must say so, not pass.
    """
    if not (ROOT / "profile.json").is_file():
        pytest.skip("no profile.json on disk; contact extraction cannot be verified")
    validate_contact(real_profile.contact)
    return real_profile.contact


@pytest.fixture()
def placeholder_profile(small_profile) -> Profile:
    """The shape of the incident: a complete profile whose contact block is scrubbed."""
    return dataclasses.replace(
        small_profile,
        contact=Contact(
            name="Simon Chen",
            email="simon@example.com",
            phone="555-555-5555",
            website="https://example.com",
            github="https://github.com/example",
            linkedin="https://linkedin.com/in/example",
        ),
    )


@pytest.fixture()
def small_profile() -> Profile:
    return Profile(
        # Deliberately not a placeholder: validate_contact rejects example.com addresses and
        # 555-exchange numbers, so a fixture using them could never exercise the apply path.
        contact=Contact(name="Simon Chen", email="simon.chen@fixture.test", phone="617-201-4477"),
        education=(Education("BU", "Boston, MA", "BA CS", "2026", ("Systems",)),),
        experiences={
            "org-a": Experience(
                "org-a", "Engineer", "OrgA", "NY", "2025", {"a1": "A one", "a2": "A two", "a3": "A three"}
            ),
            "org-b": Experience(
                "org-b", "Intern", "OrgB", "MA", "2024", {"b1": "B one", "b2": "B two", "b3": "B three"}
            ),
        },
        projects={
            "proj1": Project("proj1", "Proj1", "Python", "2025", {"p1": "P1 one", "p2": "P1 two", "p3": "P1 three"}),
            "proj2": Project("proj2", r"Proj \& Two", "Rust", "2024", {"q1": "P2 one"}),
        },
        skills={"languages": ("Python", "Rust"), "platforms_and_systems": ("AWS",)},
    )
