from __future__ import annotations

import json

import pytest

from worksisyphus import Pick, PlanError, parse_plan, sanitize_name


def _plan(**overrides) -> str:
    data = {
        "name": "acme_swe",
        "experiences": {"org-a": "all", "org-b": ["b1", "b2"]},
        "projects": {"proj1": ["p1", "p3"]},
        "skills": {"languages": ["Rust"]},
    }
    data.update(overrides)
    return json.dumps(data)


def test_parses_valid_plan(small_profile) -> None:
    selection = parse_plan(_plan(), small_profile)
    assert selection.name == "acme_swe_resume"
    assert [(p.id, p.bullets) for p in selection.experiences] == [("org-a", ("a1", "a2", "a3")), ("org-b", ("b1", "b2"))]
    assert selection.projects == (Pick("proj1", ("p1", "p3")),)
    assert selection.skills == {"languages": ("Rust",)}


def test_plan_order_is_rank(small_profile) -> None:
    plan = json.dumps({"name": "x", "experiences": {"org-b": "all", "org-a": "all"}, "projects": ["proj1"]})
    selection = parse_plan(plan, small_profile)
    assert [p.id for p in selection.experiences] == ["org-b", "org-a"]


def test_list_shorthand_means_all_bullets(small_profile) -> None:
    plan = json.dumps({"name": "x", "experiences": ["org-a"], "projects": ["proj2", "proj1"]})
    selection = parse_plan(plan, small_profile)
    assert selection.experiences[0].bullets == ("a1", "a2", "a3")
    assert [p.id for p in selection.projects] == ["proj2", "proj1"]


def test_skills_default_and_all_copy_profile(small_profile) -> None:
    for plan in (_plan(skills="all"), json.dumps({"name": "x", "experiences": ["org-a"]})):
        assert parse_plan(plan, small_profile).skills == small_profile.skills


def test_unknown_entry_slug_fails(small_profile) -> None:
    with pytest.raises(PlanError, match="Unknown experiences slug 'nope'"):
        parse_plan(_plan(experiences={"nope": "all"}), small_profile)


def test_unknown_bullet_slug_fails(small_profile) -> None:
    with pytest.raises(PlanError, match="Unknown bullet slug"):
        parse_plan(_plan(projects={"proj1": ["p1", "typo"]}), small_profile)


def test_unknown_skill_fails(small_profile) -> None:
    with pytest.raises(PlanError, match="Unknown skill"):
        parse_plan(_plan(skills={"languages": ["COBOL"]}), small_profile)


def test_unknown_top_level_key_fails(small_profile) -> None:
    with pytest.raises(PlanError, match="Unknown plan key"):
        parse_plan(_plan(experiances={"org-a": "all"}), small_profile)


def test_empty_plan_fails(small_profile) -> None:
    with pytest.raises(PlanError, match="no experiences and no projects"):
        parse_plan(json.dumps({"name": "x"}), small_profile)


def test_invalid_json_fails(small_profile) -> None:
    with pytest.raises(PlanError, match="not valid JSON"):
        parse_plan("{oops", small_profile)


def test_name_falls_back_to_default(small_profile) -> None:
    plan = json.dumps({"experiences": ["org-a"]})
    assert parse_plan(plan, small_profile, default_name="bosch").name == "bosch_resume"
    assert parse_plan(plan, small_profile).name == "tailored_resume"


def test_sanitize_name() -> None:
    assert sanitize_name("Acme Corp SWE II!") == "acme_corp_swe_ii_resume"
    assert sanitize_name("my_resume") == "my_resume"
    assert sanitize_name("") == "tailored_resume"
