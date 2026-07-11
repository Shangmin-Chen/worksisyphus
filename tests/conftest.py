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
    return load_profile(ROOT / "profile.json")


@pytest.fixture()
def small_profile() -> Profile:
    return Profile(
        contact=Contact(name="Simon Chen", email="s@example.com", phone="555-0100"),
        education=(Education("BU", "Boston, MA", "BA CS", "2026", ("Systems",)),),
        experiences={
            "org-a": Experience("org-a", "Engineer", "OrgA", "NY", "2025", {"a1": "A one", "a2": "A two", "a3": "A three"}),
            "org-b": Experience("org-b", "Intern", "OrgB", "MA", "2024", {"b1": "B one", "b2": "B two", "b3": "B three"}),
        },
        projects={
            "proj1": Project("proj1", "Proj1", "Python", "2025", {"p1": "P1 one", "p2": "P1 two", "p3": "P1 three"}),
            "proj2": Project("proj2", r"Proj \& Two", "Rust", "2024", {"q1": "P2 one"}),
        },
        skills={"languages": ("Python", "Rust"), "platforms_and_systems": ("AWS",)},
    )
