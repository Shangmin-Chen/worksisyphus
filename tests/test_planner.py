from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus import (
    GeminiPlanner,
    PLAN_CACHE_KEY_VERSION,
    PlanCache,
    build_planner_prompt,
    canonical_profile_hash,
    deterministic_fallback_selection_plan,
    get_template_spec,
    load_canonical_profile,
    normalize_selection_plan,
    parse_planner_json,
    plan_cache_key,
    planner_template_spec_hash,
    raw_input_hash,
    selection_plan_artifact_json,
)
from worksisyphus.profile import parse_canonical_profile


class PlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_canonical_profile(ROOT / "templates" / "experiences.json")
        cls.template = get_template_spec("jakes_resume")
        cls.profile_hash = canonical_profile_hash(cls.profile)

    def _valid_raw_plan(self) -> dict:
        experience = self.profile.experiences[0]
        project = self.profile.projects[0]
        languages = self.profile.skill_groups_by_id()["languages"]
        return {
            "document_type": "resume",
            "template_id": "jakes_resume",
            "target": {"company": "Acme", "role": "Software Engineer"},
            "sections": ["education", "experience", "projects", "technical_skills"],
            "education_ids": [self.profile.education[0].id],
            "experience_ids": [experience.id],
            "project_ids": [project.id],
            "bullet_ids_by_item": {
                experience.id: [experience.bullets[0].id, experience.bullets[1].id],
                project.id: [project.bullets[0].id],
            },
            "skill_ids_by_group": {"languages": [languages.skills[0].id, languages.skills[1].id]},
            "rationale": "IDs match the raw request.",
        }

    def test_parse_fenced_json(self) -> None:
        raw_plan = self._valid_raw_plan()
        parsed = parse_planner_json("```json\n" + json.dumps(raw_plan) + "\n```")

        plan = normalize_selection_plan(parsed, profile=self.profile, template_spec=self.template)

        self.assertEqual(plan.target.company, "Acme")
        self.assertEqual(plan.experience_ids, (self.profile.experiences[0].id,))

    def test_invalid_json_falls_back_and_is_cached(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = PlanCache(Path(temp_dir) / "cache")
            planner = GeminiPlanner(lambda prompt: "not json at all", cache=cache)

            result = planner.plan(raw_input="Software engineer at Acme", profile=self.profile, template_spec=self.template)
            record = cache.read_record(result.cache_key)

            self.assertTrue(result.used_fallback)
            self.assertFalse(result.from_cache)
            self.assertEqual(result.validation_status, "fallback_valid")
            self.assertEqual(result.validation_report["model"]["status"], "invalid_json")
            self.assertIsNotNone(record)
            self.assertEqual(record["raw_planner_text"], "not json at all")
            self.assertEqual(record["validation_status"], "fallback_valid")
            normalize_selection_plan(
                json.loads(record["normalized_artifact_json"]),
                profile=self.profile,
                template_spec=self.template,
            )

    def test_model_timeout_falls_back_with_clear_report(self) -> None:
        def timeout_model(prompt: str) -> str:
            raise TimeoutError("planner timed out")

        planner = GeminiPlanner(timeout_model)

        result = planner.plan(raw_input="Timeout case", profile=self.profile, template_spec=self.template)

        self.assertTrue(result.used_fallback)
        self.assertEqual(result.validation_report["model"]["status"], "model_error")
        self.assertEqual(result.validation_report["model"]["errors"][0]["code"], "TimeoutError")

    def test_unknown_id_plan_falls_back_and_reports_validator_errors(self) -> None:
        invalid_plan = self._valid_raw_plan()
        invalid_plan["experience_ids"] = ["experience:from-old-profile"]
        invalid_plan["bullet_ids_by_item"] = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            planner = GeminiPlanner(lambda prompt: json.dumps(invalid_plan), cache=PlanCache(Path(temp_dir) / "cache"))

            result = planner.plan(raw_input="Use old profile ID", profile=self.profile, template_spec=self.template)

            self.assertTrue(result.used_fallback)
            self.assertEqual(result.validation_report["model"]["status"], "invalid_plan")
            error_codes = {error["code"] for error in result.validation_report["model"]["errors"]}
            self.assertIn("unknown_experience_id", error_codes)
            self.assertEqual(result.raw_planner_json["experience_ids"], ["experience:from-old-profile"])

    def test_rationale_only_json_falls_back_as_invalid_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = GeminiPlanner(
                lambda prompt: json.dumps({"rationale": "only"}),
                cache=PlanCache(Path(temp_dir) / "cache"),
            )

            result = planner.plan(raw_input="Rationale only", profile=self.profile, template_spec=self.template)

            self.assertTrue(result.used_fallback)
            self.assertEqual(result.validation_report["model"]["status"], "invalid_plan")
            error_codes = {error["code"] for error in result.validation_report["model"]["errors"]}
            self.assertIn("missing_required_field", error_codes)
            self.assertIn("missing_selectable_content", error_codes)

    def test_partial_selection_plan_json_falls_back_as_invalid_plan(self) -> None:
        partial_plan = {
            "document_type": "resume",
            "template_id": "jakes_resume",
            "sections": ["education"],
            "education_ids": [self.profile.education[0].id],
        }

        planner = GeminiPlanner(lambda prompt: json.dumps(partial_plan))

        result = planner.plan(raw_input="Partial plan", profile=self.profile, template_spec=self.template)

        self.assertTrue(result.used_fallback)
        self.assertEqual(result.validation_report["model"]["status"], "invalid_plan")
        error_paths = {error["path"] for error in result.validation_report["model"]["errors"]}
        self.assertIn("target", error_paths)
        self.assertIn("experience_ids", error_paths)
        self.assertIn("project_ids", error_paths)
        self.assertIn("bullet_ids_by_item", error_paths)
        self.assertIn("skill_ids_by_group", error_paths)

    def test_complete_empty_plan_is_valid_when_profile_has_no_selectable_content(self) -> None:
        empty_profile = parse_canonical_profile({"contact": {"name": "Ada Lovelace"}})
        empty_plan = {
            "document_type": "resume",
            "template_id": "jakes_resume",
            "target": {},
            "sections": [],
            "education_ids": [],
            "experience_ids": [],
            "project_ids": [],
            "bullet_ids_by_item": {},
            "skill_ids_by_group": {},
            "rationale": "Nothing selectable.",
        }
        planner = GeminiPlanner(lambda prompt: json.dumps(empty_plan))

        result = planner.plan(raw_input="Empty profile", profile=empty_profile, template_spec=self.template)

        self.assertFalse(result.used_fallback)
        self.assertEqual(result.validation_status, "valid")
        self.assertEqual(result.plan.rationale, "Nothing selectable.")

    def test_exact_same_raw_request_hits_plan_cache_without_model_call(self) -> None:
        calls: list[str] = []

        def fake_model(prompt: str) -> str:
            calls.append(prompt)
            return json.dumps(self._valid_raw_plan())

        with tempfile.TemporaryDirectory() as temp_dir:
            cache = PlanCache(Path(temp_dir) / "cache")
            planner = GeminiPlanner(fake_model, cache=cache, model_id="gemini-test")

            first = planner.plan(raw_input="Acme software role", profile=self.profile, template_spec=self.template)
            second = planner.plan(raw_input="Acme software role", profile=self.profile, template_spec=self.template)
            record = cache.read_record(first.cache_key)

            self.assertEqual(len(calls), 1)
            self.assertFalse(first.from_cache)
            self.assertTrue(second.from_cache)
            self.assertFalse(second.used_fallback)
            self.assertEqual(first.cache_key, second.cache_key)
            self.assertEqual(selection_plan_artifact_json(first.plan), selection_plan_artifact_json(second.plan))
            self.assertEqual(first.plan.rationale, second.plan.rationale)
            self.assertEqual(second.plan.rationale, "IDs match the raw request.")
            self.assertEqual(record["raw_planner_json"]["target"]["company"], "Acme")
            self.assertEqual(record["validation_status"], "valid")
            self.assertIn("normalized_plan_json", record)
            self.assertIn("normalized_artifact_json", record)
            self.assertNotIn("rationale", json.loads(record["normalized_artifact_json"]))
            self.assertEqual(json.loads(record["normalized_plan_json"])["rationale"], "IDs match the raw request.")

    def test_plan_cache_key_version_is_bumped_for_full_plan_cache_records(self) -> None:
        self.assertEqual(PLAN_CACHE_KEY_VERSION, "plan-cache-key-v2")

    def test_cache_key_changes_with_raw_prompt_model_schema_profile_or_template(self) -> None:
        base = {
            "raw_input_hash_value": raw_input_hash("raw one"),
            "canonical_profile_hash_value": "profile-one",
            "template_id": "jakes_resume",
            "prompt_version": "prompt-v1",
            "model_id": "model-a",
            "planner_schema_version": "schema-v1",
        }
        base_key = plan_cache_key(**base)
        base_with_template = {**base, "template_spec_hash_value": planner_template_spec_hash(self.template)}
        variations = [
            {**base, "raw_input_hash_value": raw_input_hash("raw two")},
            {**base, "canonical_profile_hash_value": "profile-two"},
            {**base, "template_id": "other_template"},
            {**base, "prompt_version": "prompt-v2"},
            {**base, "model_id": "model-b"},
            {**base, "planner_schema_version": "schema-v2"},
            {
                **base_with_template,
                "template_spec_hash_value": planner_template_spec_hash(
                    replace(self.template, max_experiences=self.template.max_experiences + 1)
                ),
            },
        ]

        for variation in variations:
            with self.subTest(variation=variation):
                comparison_key = plan_cache_key(**base_with_template) if "template_spec_hash_value" in variation else base_key
                self.assertNotEqual(comparison_key, plan_cache_key(**variation))

    def test_prompt_has_no_final_document_instructions_and_document_command_output_is_rejected(self) -> None:
        profile = parse_canonical_profile(
            {
                "contact": {"name": "Ada Lovelace"},
                "experiences": [
                    {
                        "organization": "Acme",
                        "role": "Engineer",
                        "date": "2026",
                        "bullets": ["Built deterministic planners."],
                    }
                ],
                "skills": {"languages": ["Python"]},
            }
        )
        prompt = build_planner_prompt(raw_input="Plain job description", profile=profile, template_spec=self.template)
        lowered_prompt = prompt.lower()

        self.assertNotIn("latex", lowered_prompt)
        self.assertNotIn("\\documentclass", prompt)
        self.assertNotIn("source_template", prompt)
        self.assertNotIn(".tex", lowered_prompt)
        self.assertNotIn("compile", lowered_prompt)
        self.assertNotIn("render", lowered_prompt)

        with tempfile.TemporaryDirectory() as temp_dir:
            planner = GeminiPlanner(
                lambda prompt: "\\documentclass{article}\\begin{document}bad\\end{document}",
                cache=PlanCache(Path(temp_dir) / "cache"),
            )
            result = planner.plan(raw_input="Plain job description", profile=profile, template_spec=self.template)

            self.assertTrue(result.used_fallback)
            self.assertEqual(result.validation_report["model"]["status"], "invalid_json")

    def test_fallback_plan_validates_and_uses_template_order(self) -> None:
        plan = deterministic_fallback_selection_plan(profile=self.profile, template_spec=self.template)
        round_tripped = normalize_selection_plan(
            json.loads(selection_plan_artifact_json(plan)),
            profile=self.profile,
            template_spec=self.template,
        )

        self.assertEqual(round_tripped.sections, self.template.section_order)
        self.assertLessEqual(len(round_tripped.experience_ids), self.template.max_experiences)
        self.assertEqual(round_tripped.experience_ids, tuple(entry.id for entry in self.profile.experiences[:3]))
        first_experience = self.profile.experiences[0]
        bullets_by_item = dict(round_tripped.bullet_ids_by_item)
        self.assertEqual(
            bullets_by_item[first_experience.id],
            tuple(bullet.id for bullet in first_experience.bullets[: self.template.max_bullets_per_experience]),
        )


if __name__ == "__main__":
    unittest.main()
