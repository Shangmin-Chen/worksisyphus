from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus import (
    ArtifactStore,
    InvalidPdfArtifactError,
    artifact_cache_key,
    canonical_profile_hash,
    get_template_spec,
    load_canonical_profile,
    normalize_selection_plan,
)


class ArtifactCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_canonical_profile(ROOT / "templates" / "experiences.json")
        cls.template = get_template_spec("jakes_resume")
        cls.profile_hash = canonical_profile_hash(cls.profile)

    def _raw_plan(self, *, experience_order: list[str] | None = None, bullet_order: list[str] | None = None) -> dict:
        first_experience = self.profile.experiences[0]
        second_experience = self.profile.experiences[1]
        project = self.profile.projects[0]
        languages = self.profile.skill_groups_by_id()["languages"]
        selected_experiences = experience_order or [first_experience.id, second_experience.id]
        first_bullets = bullet_order or [first_experience.bullets[0].id, first_experience.bullets[1].id]
        return {
            "document_type": "resume",
            "template_id": "jakes_resume",
            "sections": ["education", "experience", "projects", "technical_skills"],
            "education_ids": [self.profile.education[0].id],
            "experience_ids": selected_experiences,
            "project_ids": [project.id],
            "bullet_ids_by_item": {
                first_experience.id: first_bullets,
                second_experience.id: [second_experience.bullets[0].id],
                project.id: [project.bullets[0].id],
            },
            "skill_ids_by_group": {"languages": [languages.skills[0].id, languages.skills[1].id]},
        }

    def _key_for_raw_plan(self, raw_plan: dict) -> str:
        plan = normalize_selection_plan(raw_plan, profile=self.profile, template_spec=self.template)
        return artifact_cache_key(
            selection_plan=plan,
            template_spec=self.template,
            canonical_profile_hash_value=self.profile_hash,
        )

    def test_artifact_key_ignores_rationale(self) -> None:
        first = self._raw_plan()
        second = self._raw_plan()
        first["rationale"] = "First explanation."
        second["rationale"] = "Different explanation."

        self.assertEqual(self._key_for_raw_plan(first), self._key_for_raw_plan(second))

    def test_order_sensitive_plan_fields_change_artifact_key(self) -> None:
        first_experience = self.profile.experiences[0]
        second_experience = self.profile.experiences[1]
        normal = self._raw_plan()
        reversed_experiences = self._raw_plan(
            experience_order=[second_experience.id, first_experience.id],
        )
        reversed_bullets = self._raw_plan(
            bullet_order=[first_experience.bullets[1].id, first_experience.bullets[0].id],
        )

        normal_key = self._key_for_raw_plan(normal)

        self.assertNotEqual(normal_key, self._key_for_raw_plan(reversed_experiences))
        self.assertNotEqual(normal_key, self._key_for_raw_plan(reversed_bullets))

    def test_artifact_store_caches_and_exports_tex_and_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = ArtifactStore(root / "cache")
            first_key = "a" * 64
            second_key = "b" * 64
            output_path = root / "exports" / "resume.tex"
            pdf_path = root / "exports" / "resume.pdf"

            record = store.cache_tex(key=first_key, tex="first tex\n", metadata={"job": "one"})
            first_export = store.export_tex(key=first_key, output_path=output_path)

            self.assertTrue(record.tex_path.is_file())
            self.assertTrue(record.metadata_path.is_file())
            self.assertTrue(first_export.exported)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "first tex\n")

            store.cache_tex(key=second_key, tex="second tex\n")
            second_export = store.export_tex(key=second_key, output_path=output_path)

            self.assertTrue(second_export.exported)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "second tex\n")
            with self.assertRaises(FileNotFoundError):
                store.export_pdf(key=second_key, output_path=pdf_path)

            compiled_pdf = root / "build" / "resume.pdf"
            compiled_pdf.parent.mkdir()
            compiled_pdf.write_bytes(b"%PDF-1.7\ncompiled pdf\n")
            cached_pdf_path = store.cache_pdf_from_path(
                key=second_key,
                pdf_path=compiled_pdf,
                compile_metadata={"ok": True, "engine": "pdflatex"},
            )
            pdf_export = store.export_pdf(key=second_key, output_path=pdf_path)
            metadata = store.read_metadata(second_key)

            self.assertEqual(cached_pdf_path.read_bytes(), b"%PDF-1.7\ncompiled pdf\n")
            self.assertTrue(pdf_export.exported)
            self.assertEqual(pdf_path.read_bytes(), b"%PDF-1.7\ncompiled pdf\n")
            self.assertTrue(metadata["has_pdf"])
            self.assertEqual(metadata["pdf_status"], "compiled")

    def test_artifact_store_rejects_non_pdf_source_without_claiming_compiled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = ArtifactStore(root / "cache")
            key = "invalid-source-key"
            source_pdf = root / "build" / "resume.pdf"
            source_pdf.parent.mkdir()
            source_pdf.write_bytes(b"not a pdf\n")

            store.cache_tex(key=key, tex="trusted tex\n")
            before_metadata = store.read_metadata(key)

            with self.assertRaises(InvalidPdfArtifactError):
                store.cache_pdf_from_path(
                    key=key,
                    pdf_path=source_pdf,
                    compile_metadata={"ok": True, "engine": "pdflatex"},
                )

            after_metadata = store.read_metadata(key)
            self.assertFalse(store.pdf_path(key).exists())
            self.assertEqual(after_metadata, before_metadata)
            self.assertFalse(after_metadata["has_pdf"])
            self.assertEqual(after_metadata["pdf_status"], "not_compiled")

    def test_export_pdf_rejects_invalid_cached_bytes_and_preserves_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = ArtifactStore(root / "cache")
            key = "invalid-cached-key"
            output = root / "exports" / "resume.pdf"
            output.parent.mkdir()
            output.write_bytes(b"%PDF-1.7\nprevious export\n")

            store.artifact_dir(key).mkdir(parents=True)
            store.pdf_path(key).write_bytes(b"not a pdf\n")

            with self.assertRaises(InvalidPdfArtifactError):
                store.export_pdf(key=key, output_path=output)

            self.assertEqual(output.read_bytes(), b"%PDF-1.7\nprevious export\n")

    def test_cache_compile_log_ok_without_pdf_does_not_claim_compiled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtifactStore(Path(temp_dir) / "cache")
            key = "dishonest-log-key"

            log_path = store.cache_compile_log(
                key=key,
                log_text="engine reported success but no PDF exists\n",
                compile_metadata={"ok": True, "engine": "pdflatex", "returncode": 0},
            )
            metadata = store.read_metadata(key)

            self.assertTrue(log_path.is_file())
            self.assertTrue(metadata["has_log"])
            self.assertFalse(metadata["has_pdf"])
            self.assertEqual(metadata["pdf_status"], "compile_succeeded_no_pdf")
            self.assertNotEqual(metadata["pdf_status"], "compiled")
            self.assertTrue(metadata["last_compile"]["ok"])


if __name__ == "__main__":
    unittest.main()
