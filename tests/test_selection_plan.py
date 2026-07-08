from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus import (
    PlanValidationError,
    build_render_model,
    get_template_spec,
    load_canonical_profile,
    normalize_selection_plan,
    selection_plan_artifact_json,
)
from worksisyphus.profile import parse_canonical_profile


class SelectionPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_canonical_profile(ROOT / "templates" / "experiences.json")
        cls.template = get_template_spec("jakes_resume")

    def _valid_raw_plan(self) -> dict:
        education = self.profile.education[0]
        experience = self.profile.experiences[0]
        project = self.profile.projects[0]
        languages = self.profile.skill_groups_by_id()["languages"]

        return {
            "document_type": "resume",
            "template_id": "jakes_resume",
            "target": {"company": "Example Co", "role": "Software Engineer"},
            "sections": ["Education", " EXPERIENCE ", "projects", "technical_skills"],
            "education_ids": [education.id],
            "experience_ids": [f" {experience.id.upper()} "],
            "project_ids": [project.id],
            "bullet_ids_by_item": {
                f" {experience.id.upper()} ": [
                    experience.bullets[0].id.upper(),
                    experience.bullets[1].id,
                ],
                project.id: [project.bullets[0].id],
            },
            "skill_ids_by_group": {"languages": [languages.skills[1].id, languages.skills[-1].id]},
            "rationale": "Useful for diagnostics but not artifact identity.",
        }

    def assertValidationCodes(self, raw_plan: dict, expected_code: str) -> None:
        with self.assertRaises(PlanValidationError) as raised:
            normalize_selection_plan(raw_plan, profile=self.profile, template_spec=self.template)

        self.assertIn(expected_code, {error.code for error in raised.exception.errors})

    def test_valid_plan_normalizes_ids_and_builds_render_model(self) -> None:
        raw_plan = self._valid_raw_plan()
        plan = normalize_selection_plan(raw_plan, profile=self.profile, template_spec=self.template)

        experience = self.profile.experiences[0]
        self.assertEqual(plan.sections, ("education", "experience", "projects", "technical_skills"))
        self.assertEqual(plan.experience_ids, (experience.id,))
        self.assertEqual(plan.bullet_ids_by_item[0][0], experience.id)

        render_model = build_render_model(profile=self.profile, selection_plan=plan, template_spec=self.template)
        self.assertEqual(render_model.target.company, "Example Co")
        self.assertEqual(render_model.experiences[0].entry.id, experience.id)
        self.assertEqual(len(render_model.experiences[0].bullets), 2)

    def test_empty_bullet_list_entries_are_dropped_not_rejected(self) -> None:
        raw_plan = self._valid_raw_plan()
        education = self.profile.education[0]
        raw_plan["bullet_ids_by_item"][education.id] = []

        plan = normalize_selection_plan(raw_plan, profile=self.profile, template_spec=self.template)

        owner_ids = [item_id for item_id, _ in plan.bullet_ids_by_item]
        self.assertNotIn(education.id, owner_ids)
        self.assertTrue(all(bullet_ids for _, bullet_ids in plan.bullet_ids_by_item))

    def test_omitted_sections_default_to_template_order(self) -> None:
        raw_plan = self._valid_raw_plan()
        raw_plan.pop("sections")

        plan = normalize_selection_plan(raw_plan, profile=self.profile, template_spec=self.template)

        self.assertEqual(plan.sections, self.template.section_order)

    def test_unknown_ids_are_rejected(self) -> None:
        cases = [
            ("sections", ["education", "portfolio"], "unknown_section_id"),
            ("education_ids", ["education:missing"], "unknown_education_id"),
            ("experience_ids", ["experience:missing"], "unknown_experience_id"),
            ("project_ids", ["project:missing"], "unknown_project_id"),
            ("bullet_ids_by_item", {self.profile.experiences[0].id: ["experience:missing:bullet-1"]}, "unknown_bullet_id"),
            ("skill_ids_by_group", {"missing": []}, "unknown_skill_group_id"),
            ("skill_ids_by_group", {"languages": ["skill:languages:missing"]}, "unknown_skill_id"),
        ]

        for field, value, code in cases:
            with self.subTest(field=field):
                raw_plan = self._valid_raw_plan()
                raw_plan[field] = value
                self.assertValidationCodes(raw_plan, code)

    def test_duplicate_ids_are_rejected_after_normalization(self) -> None:
        raw_plan = self._valid_raw_plan()
        experience_id = self.profile.experiences[0].id
        raw_plan["experience_ids"] = [experience_id, f" {experience_id.upper()} "]

        self.assertValidationCodes(raw_plan, "duplicate_id")

    def test_duplicate_mapping_keys_are_rejected_after_normalization(self) -> None:
        raw_plan = self._valid_raw_plan()
        experience = self.profile.experiences[0]
        raw_plan["bullet_ids_by_item"] = {
            experience.id: [experience.bullets[0].id],
            f" {experience.id.upper()} ": [experience.bullets[1].id],
        }

        self.assertValidationCodes(raw_plan, "duplicate_id")

    def test_project_bullet_under_experience_is_rejected(self) -> None:
        raw_plan = self._valid_raw_plan()
        experience = self.profile.experiences[0]
        project = self.profile.projects[0]
        raw_plan["bullet_ids_by_item"] = {experience.id: [project.bullets[0].id]}

        self.assertValidationCodes(raw_plan, "wrong_bullet_owner")

    def test_unselected_bullet_owner_is_rejected(self) -> None:
        raw_plan = self._valid_raw_plan()
        selected_experience = self.profile.experiences[0]
        unselected_experience = self.profile.experiences[1]
        raw_plan["experience_ids"] = [selected_experience.id]
        raw_plan["bullet_ids_by_item"] = {
            selected_experience.id: [selected_experience.bullets[0].id],
            unselected_experience.id: [unselected_experience.bullets[0].id],
        }

        self.assertValidationCodes(raw_plan, "unselected_bullet_owner_id")

    def test_over_limit_item_counts_are_rejected(self) -> None:
        raw_plan = self._valid_raw_plan()
        raw_plan["project_ids"] = [project.id for project in self.profile.projects[:3]]

        self.assertValidationCodes(raw_plan, "limit_exceeded")

    def test_over_limit_bullet_counts_are_rejected(self) -> None:
        raw_plan = self._valid_raw_plan()
        project = self.profile.projects[1]
        raw_plan["project_ids"] = [project.id]
        raw_plan["bullet_ids_by_item"] = {project.id: [bullet.id for bullet in project.bullets[:5]]}

        self.assertValidationCodes(raw_plan, "limit_exceeded")

    def test_template_skill_group_order_constrains_allowed_groups(self) -> None:
        profile = parse_canonical_profile(
            {
                "contact": {"name": "Candidate"},
                "skills": {"languages": ["Python"], "hobbies": ["Chess"]},
            }
        )
        hobbies = profile.skill_groups_by_id()["hobbies"]
        raw_plan = {
            "document_type": "resume",
            "template_id": "jakes_resume",
            "skill_ids_by_group": {"hobbies": [hobbies.skills[0].id]},
        }

        with self.assertRaises(PlanValidationError) as raised:
            normalize_selection_plan(raw_plan, profile=profile, template_spec=self.template)

        self.assertIn("disallowed_skill_group_id", {error.code for error in raised.exception.errors})

    def test_wrong_skill_group_is_rejected(self) -> None:
        raw_plan = self._valid_raw_plan()
        framework = self.profile.skills_by_group_id()["frameworks_and_libraries"]["skill:frameworks_and_libraries:react"]
        raw_plan["skill_ids_by_group"] = {"languages": [framework.id]}

        self.assertValidationCodes(raw_plan, "wrong_skill_group")

    def test_over_limit_skills_per_group_is_rejected(self) -> None:
        raw_plan = self._valid_raw_plan()
        languages = self.profile.skill_groups_by_id()["languages"]
        raw_plan["skill_ids_by_group"] = {"languages": [skill.id for skill in languages.skills]}

        self.assertValidationCodes(raw_plan, "limit_exceeded")

    def test_artifact_serialization_is_deterministic_and_excludes_rationale(self) -> None:
        first_raw_plan = self._valid_raw_plan()
        second_raw_plan = copy.deepcopy(first_raw_plan)
        first_raw_plan["rationale"] = "First rationale."
        second_raw_plan["rationale"] = "Different rationale."
        second_raw_plan = {
            "rationale": second_raw_plan["rationale"],
            "skill_ids_by_group": second_raw_plan["skill_ids_by_group"],
            "bullet_ids_by_item": second_raw_plan["bullet_ids_by_item"],
            "project_ids": second_raw_plan["project_ids"],
            "experience_ids": second_raw_plan["experience_ids"],
            "education_ids": second_raw_plan["education_ids"],
            "sections": second_raw_plan["sections"],
            "target": second_raw_plan["target"],
            "template_id": second_raw_plan["template_id"],
            "document_type": second_raw_plan["document_type"],
        }

        first_plan = normalize_selection_plan(first_raw_plan, profile=self.profile, template_spec=self.template)
        second_plan = normalize_selection_plan(second_raw_plan, profile=self.profile, template_spec=self.template)

        first_json = selection_plan_artifact_json(first_plan)
        second_json = selection_plan_artifact_json(second_plan)

        self.assertEqual(first_json, second_json)
        self.assertNotIn("rationale", first_json)
        self.assertEqual(first_json, selection_plan_artifact_json(first_plan))


if __name__ == "__main__":
    unittest.main()
