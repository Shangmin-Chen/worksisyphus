from __future__ import annotations

from worksisyphus import profile_index


def test_real_profile_loads_expected_shape(real_profile) -> None:
    assert real_profile.contact.name == "Simon Chen"
    assert len(real_profile.experiences) == 3
    assert len(real_profile.projects) == 8
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
