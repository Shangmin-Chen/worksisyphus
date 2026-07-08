from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus.profile import ProfileValidationError, load_canonical_profile, parse_canonical_profile


class ProfileIdTests(unittest.TestCase):
    def test_legacy_ids_are_derived_from_stable_fields(self) -> None:
        profile = load_canonical_profile(ROOT / "templates" / "experiences.json")

        experience = profile.experiences[0]
        self.assertEqual(
            experience.id,
            "experience:ezesports-technical-director-software-engineer-december-2025-present",
        )
        self.assertEqual(
            experience.bullets[0].id,
            "experience:ezesports-technical-director-software-engineer-december-2025-present:bullet-1",
        )

        project = profile.projects[0]
        self.assertEqual(project.id, "project:hermes-letters-june-2026")
        self.assertEqual(project.bullets[0].id, "project:hermes-letters-june-2026:bullet-1")

        education = profile.education[0]
        self.assertEqual(
            education.id,
            "education:boston-university-bachelor-of-arts-in-computer-science-graduated-spring-2026",
        )

        languages = profile.skill_groups_by_id()["languages"]
        self.assertEqual(languages.skills[0].id, "skill:languages:c-17")
        self.assertEqual(languages.skills[-1].id, "skill:languages:typescript")

    def test_derived_id_collisions_are_rejected(self) -> None:
        raw_profile = {
            "contact": {"name": "Candidate"},
            "experiences": [
                {
                    "organization": "Acme",
                    "role": "Engineer",
                    "date": "2026",
                    "location": "NY",
                    "bullets": ["Built systems."],
                },
                {
                    "organization": "Acme",
                    "role": "Engineer",
                    "date": "2026",
                    "location": "Remote",
                    "bullets": ["Built other systems."],
                },
            ],
        }

        with self.assertRaises(ProfileValidationError) as raised:
            parse_canonical_profile(raw_profile)

        self.assertEqual(raised.exception.errors[0].code, "duplicate_id")
        self.assertEqual(raised.exception.errors[0].identifier, "experience:acme-engineer-2026")

    def test_skill_group_public_ids_collide_with_other_selectable_ids(self) -> None:
        raw_profile = {
            "contact": {"name": "Candidate"},
            "experiences": [
                {
                    "id": "languages",
                    "organization": "Acme",
                    "role": "Engineer",
                    "date": "2026",
                    "location": "Remote",
                    "bullets": ["Built systems."],
                }
            ],
            "skills": {"languages": ["Python"]},
        }

        with self.assertRaises(ProfileValidationError) as raised:
            parse_canonical_profile(raw_profile)

        self.assertIn("duplicate_id", {error.code for error in raised.exception.errors})
        self.assertIn("languages", {error.identifier for error in raised.exception.errors})

    def test_latex_special_character_bullets_are_preserved_unescaped(self) -> None:
        bullet_text = r"C++ & 50% of $x_1$ # {ok} ~ ^ \\"
        raw_profile = {
            "contact": {"name": "Candidate"},
            "experiences": [
                {
                    "organization": "Acme",
                    "role": "Engineer",
                    "date": "2026",
                    "location": "Remote",
                    "bullets": [bullet_text],
                }
            ],
        }

        profile = parse_canonical_profile(raw_profile)

        self.assertEqual(profile.experiences[0].bullets[0].text, bullet_text)


if __name__ == "__main__":
    unittest.main()
