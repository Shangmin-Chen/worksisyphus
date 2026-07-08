from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus import build_render_model, escape_latex, get_template_spec, normalize_selection_plan, render_tex
from worksisyphus.profile import parse_canonical_profile


class RendererEscapeTests(unittest.TestCase):
    def test_escape_latex_covers_special_characters(self) -> None:
        text = "C++ & 50% of $x_1$ # {ok} ~ ^ \\ " + "\u00b5 \u03bc \u2013"

        self.assertEqual(
            escape_latex(text),
            r"C++ \& 50\% of \$x\_1\$ \# \{ok\} \textasciitilde{} "
            r"\textasciicircum{} \textbackslash{} \ensuremath{\mu} \ensuremath{\mu} --",
        )

    def test_renderer_escapes_canonical_text(self) -> None:
        special_bullet = "Reduced query latency to 20\u03bcs while keeping C++ & $x_1$ safe."
        profile = parse_canonical_profile(
            {
                "contact": {"name": "A_B"},
                "experiences": [
                    {
                        "organization": "R&D {Lab}",
                        "location": "NY_1",
                        "role": "TeX Safety Engineer",
                        "date": "2026",
                        "bullets": [special_bullet],
                    }
                ],
            }
        )
        template = get_template_spec("jakes_resume")
        experience = profile.experiences[0]
        plan = normalize_selection_plan(
            {
                "document_type": "resume",
                "template_id": "jakes_resume",
                "sections": ["experience"],
                "experience_ids": [experience.id],
                "bullet_ids_by_item": {experience.id: [experience.bullets[0].id]},
            },
            profile=profile,
            template_spec=template,
        )
        render_model = build_render_model(profile=profile, selection_plan=plan, template_spec=template)

        rendered = render_tex(render_model, template)

        self.assertIn(r"\textbf{\Huge \scshape A\_B}", rendered)
        self.assertIn(r"{R\&D \{Lab\}}{NY\_1}", rendered)
        self.assertIn(
            r"\resumeItem{Reduced query latency to 20\ensuremath{\mu}s "
            r"while keeping C++ \& \$x\_1\$ safe.}",
            rendered,
        )
        self.assertNotIn("\u03bc", rendered)
        self.assertNotIn(special_bullet, rendered)


if __name__ == "__main__":
    unittest.main()
