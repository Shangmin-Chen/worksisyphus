from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus import BUILTIN_TEMPLATE_SPECS, get_template_spec


class TemplateSpecTests(unittest.TestCase):
    def test_resume_template_spec_matches_current_template_contract(self) -> None:
        spec = get_template_spec("jakes_resume")

        self.assertEqual(spec.document_type, "resume")
        self.assertEqual(spec.source_template, "templates/resumes/jakes_resume_template.tex")
        self.assertEqual(spec.section_order, ("education", "experience", "projects", "technical_skills"))
        self.assertEqual(spec.max_experiences, 3)
        self.assertEqual(spec.max_projects, 2)
        self.assertEqual(spec.max_bullets_per_experience, 3)
        self.assertEqual(spec.max_bullets_per_project, 4)

    def test_cover_letter_template_spec_is_registered(self) -> None:
        spec = get_template_spec("default_cover_letter")

        self.assertEqual(spec.document_type, "cover_letter")
        self.assertEqual(spec.source_template, "templates/cover_letters/default_cover_letter.tex")
        self.assertEqual(spec.section_order, ("letter_body", "supporting_bullets"))
        self.assertIn("default_cover_letter", BUILTIN_TEMPLATE_SPECS)


if __name__ == "__main__":
    unittest.main()
