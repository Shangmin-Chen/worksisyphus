from __future__ import annotations

import json

import pytest

from worksisyphus import PlanError, parse_plan, plan_selection, sanitize_name


def _valid_response() -> dict:
    return {
        "name": "acme_platform_engineer",
        "experiences": [{"id": "E1", "bullets": [1, 3]}, {"id": "E2", "bullets": [2]}],
        "projects": [{"id": "P1", "bullets": [1, 2]}],
        "skills": {"languages": ["Python"], "platforms_and_systems": ["AWS"]},
    }


def test_valid_plan_parses_ranked_zero_based(small_profile) -> None:
    selection = parse_plan(json.dumps(_valid_response()), small_profile)
    assert selection.name == "acme_platform_engineer_resume"
    assert selection.experiences[0].bullets == (0, 2)
    assert selection.experiences[1] .index == 1
    assert selection.projects[0].bullets == (0, 1)
    assert selection.skills == {"languages": ("Python",), "platforms_and_systems": ("AWS",)}


def test_markdown_fences_are_tolerated(small_profile) -> None:
    wrapped = "```json\n" + json.dumps(_valid_response()) + "\n```"
    assert parse_plan(wrapped, small_profile).name == "acme_platform_engineer_resume"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["experiences"].append({"id": "E9", "bullets": [1]}),
        lambda d: d["experiences"][0].update(bullets=[7]),
        lambda d: d.update(experiences=[]),
        lambda d: d.update(projects=[]),
        lambda d: d.update(skills={"made_up_group": ["Python"]}),
        lambda d: d["projects"][0].update(bullets=[]),
    ],
)
def test_invalid_plans_fail_closed(small_profile, mutate) -> None:
    data = _valid_response()
    mutate(data)
    with pytest.raises(PlanError):
        parse_plan(json.dumps(data), small_profile)


def test_non_json_fails_closed(small_profile) -> None:
    with pytest.raises(PlanError):
        parse_plan("Sure! Here is the plan you asked for.", small_profile)


def test_unlisted_skills_are_dropped_not_invented(small_profile) -> None:
    data = _valid_response()
    data["skills"]["languages"] = ["Python", "COBOL"]
    selection = parse_plan(json.dumps(data), small_profile)
    assert selection.skills["languages"] == ("Python",)


def test_sanitize_name() -> None:
    assert sanitize_name("Bosch SWE-II!") == "bosch_swe_ii_resume"
    assert sanitize_name("") == "tailored_resume"
    assert sanitize_name("acme_resume") == "acme_resume"


def test_plan_selection_uses_injected_model(small_profile) -> None:
    prompts: list[str] = []

    def fake_model(prompt: str) -> str:
        prompts.append(prompt)
        return json.dumps(_valid_response())

    selection = plan_selection("Great job description.", small_profile, call_model=fake_model)
    assert selection.name == "acme_platform_engineer_resume"
    assert "Great job description." in prompts[0]
    assert "E1:" in prompts[0] and "P2:" in prompts[0]
