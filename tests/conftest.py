from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus import Profile, load_profile  # noqa: E402
from worksisyphus.profile import Contact, Education, Experience, Project  # noqa: E402


@pytest.fixture(scope="session")
def real_profile() -> Profile:
    return load_profile(ROOT / "templates" / "experiences.json")


@pytest.fixture()
def small_profile() -> Profile:
    return Profile(
        contact=Contact(name="Simon Chen", email="s@example.com", phone="555-0100"),
        education=(Education("BU", "Boston, MA", "BA CS", "2026", ("Systems",)),),
        experiences=(
            Experience("OrgA", "NY", "Engineer", "2025", ("A one", "A two", "A three")),
            Experience("OrgB", "MA", "Intern", "2024", ("B one", "B two", "B three")),
        ),
        projects=(
            Project("Proj1", "Python", "2025", ("P1 one", "P1 two", "P1 three")),
            Project(r"Proj \& Two", "Rust", "2024", ("P2 one",)),
        ),
        skills={"languages": ("Python", "Rust"), "platforms_and_systems": ("AWS",)},
    )
