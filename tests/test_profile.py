from __future__ import annotations

from worksisyphus import planner_index


def test_real_profile_loads_expected_shape(real_profile) -> None:
    assert real_profile.contact.name == "Simon Chen"
    assert len(real_profile.experiences) == 3
    assert len(real_profile.projects) == 8
    persephone = next(p for p in real_profile.projects if p.name == "Persephone")
    assert len(persephone.bullets) == 8
    assert persephone.technologies == "Python, Cython/C++17, Rust, Modal, FAISS"
    assert set(real_profile.skills) == {
        "languages",
        "frameworks_and_libraries",
        "databases_and_infrastructure",
        "platforms_and_systems",
    }


def test_planner_index_ids_and_bullets(small_profile) -> None:
    index = planner_index(small_profile)
    assert "E1: Engineer at OrgA (2025)" in index
    assert "E2.2: B two" in index
    assert "P2:" in index
    assert "languages: Python, Rust" in index


def test_values_stay_verbatim_tex(real_profile) -> None:
    joined = planner_index(real_profile)
    assert r"\$8K" in joined
    assert r"$\sim$20$\mu$s" in joined
