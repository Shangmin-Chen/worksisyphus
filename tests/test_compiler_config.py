"""Tests for CompilerConfig toggles, coursework modes, and Jake's template formatting."""

from __future__ import annotations

from dataclasses import replace

from worksisyphus.core.domain.models import CompilerConfig, CourseworkMode, Profile, Selection
from worksisyphus.core.rendering.latex import render_resume


def _make_test_profile(small_profile: Profile, gpa: str | None = "3.85") -> Profile:
    edu = small_profile.education[0]
    updated_edu = replace(
        edu,
        gpa=gpa,
        coursework=("CS 101", "CS 102", "CS 201", "CS 202", "CS 301", "CS 302"),
    )
    return replace(small_profile, education=(updated_edu,))


def _make_selection(small_profile: Profile) -> Selection:
    from worksisyphus.core.domain.rules import full_selection

    return full_selection(small_profile)


def test_compiler_config_defaults() -> None:
    config = CompilerConfig()
    assert not config.include_gpa
    assert config.coursework_mode == CourseworkMode.FULL
    assert config.include_locations
    assert config.clickable_links
    assert not config.compact_skills
    assert not config.compact_header
    assert not config.enable_density_ladder


def test_education_gpa_suppressed_by_default(small_profile: Profile) -> None:
    profile = _make_test_profile(small_profile, gpa="3.85")
    selection = _make_selection(profile)

    tex = render_resume(profile, selection, config=CompilerConfig())
    assert "3.85" not in tex
    assert "GPA" not in tex


def test_education_gpa_emitted_when_explicitly_toggled(small_profile: Profile) -> None:
    profile = _make_test_profile(small_profile, gpa="3.85")
    selection = _make_selection(profile)

    tex = render_resume(profile, selection, config=CompilerConfig(include_gpa=True))
    assert "GPA: 3.85" in tex


def test_coursework_mode_full(small_profile: Profile) -> None:
    profile = _make_test_profile(small_profile)
    selection = _make_selection(profile)

    tex = render_resume(profile, selection, config=CompilerConfig(coursework_mode=CourseworkMode.FULL))
    assert "Relevant Coursework: CS 101, CS 102, CS 201, CS 202, CS 301, CS 302." in tex


def test_coursework_mode_condensed(small_profile: Profile) -> None:
    profile = _make_test_profile(small_profile)
    selection = _make_selection(profile)

    tex = render_resume(profile, selection, config=CompilerConfig(coursework_mode=CourseworkMode.CONDENSED))
    assert "Relevant Coursework: CS 101, CS 102, CS 201, CS 202." in tex
    assert "CS 301" not in tex


def test_coursework_mode_none(small_profile: Profile) -> None:
    profile = _make_test_profile(small_profile)
    selection = _make_selection(profile)

    tex = render_resume(profile, selection, config=CompilerConfig(coursework_mode=CourseworkMode.NONE))
    assert "Relevant Coursework" not in tex


def test_compact_skills_toggle(small_profile: Profile) -> None:
    selection = _make_selection(small_profile)

    standard_tex = render_resume(small_profile, selection, config=CompilerConfig(compact_skills=False))
    compact_tex = render_resume(small_profile, selection, config=CompilerConfig(compact_skills=True))

    assert r"\\" in standard_tex
    assert "$|$" in compact_tex


def test_include_locations_toggle(small_profile: Profile) -> None:
    selection = _make_selection(small_profile)

    with_loc = render_resume(small_profile, selection, config=CompilerConfig(include_locations=True))
    without_loc = render_resume(small_profile, selection, config=CompilerConfig(include_locations=False))

    loc = small_profile.education[0].location
    assert loc in with_loc
    assert rf"{{{loc}}}" not in without_loc
