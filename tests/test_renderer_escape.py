from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus import build_render_model, get_template_spec, normalize_selection_plan, render_tex, tex_text
from worksisyphus.profile import parse_canonical_profile


class RendererTexPassthroughTests(unittest.TestCase):
    def test_tex_text_passes_tex_markup_through_verbatim(self) -> None:
        text = r"generated \$8K net PnL, cut latency by 75\% ($\sim$20$\mu$s), Data \& Algorithms"

        self.assertEqual(tex_text(text), text)
        self.assertEqual(tex_text(None), "")

    def test_renderer_preserves_canonical_tex_values(self) -> None:
        tex_bullet = r"Reduced query latency from $\sim$1.5ms to $\sim$20$\mu$s per query ($\sim$75x), a 98\% cut."
        profile = parse_canonical_profile(
            {
                "contact": {"name": "Simon Chen"},
                "experiences": [
                    {
                        "organization": r"R\&D Lab",
                        "location": "NY",
                        "role": "TeX Engineer",
                        "date": "2026",
                        "bullets": [tex_bullet],
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

        self.assertIn(rf"\resumeItem{{{tex_bullet}}}", rendered)
        self.assertIn(r"{R\&D Lab}{NY}", rendered)
        self.assertNotIn(r"\textbackslash", rendered)
        self.assertNotIn(r"\textasciitilde", rendered)


if __name__ == "__main__":
    unittest.main()
