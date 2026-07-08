from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import generate as generate_cli
from worksisyphus import load_canonical_profile


class FakeCompilerBackend:
    calls: list[dict[str, object]] = []

    def __init__(self, artifact_store) -> None:
        self.artifact_store = artifact_store

    def compile_render_model(self, *, render_model, template_spec, key, output_pdf_path=None, metadata=None):
        self.calls.append(
            {
                "render_model": render_model,
                "template_spec": template_spec,
                "key": key,
                "output_pdf_path": output_pdf_path,
            }
        )
        source_pdf = self.artifact_store.cache_dir / "fake-build" / "resume.pdf"
        source_pdf.parent.mkdir(parents=True, exist_ok=True)
        source_pdf.write_bytes(b"%PDF-1.7\nfake compiled pdf\n")
        cached_pdf = self.artifact_store.cache_pdf_from_path(
            key=key,
            pdf_path=source_pdf,
            metadata=metadata,
            compile_metadata={"ok": True, "engine": "fake", "returncode": 0},
        )
        log_path = self.artifact_store.cache_compile_log(
            key=key,
            log_text="fake compile ok\n",
            metadata=metadata,
            compile_metadata={"ok": True, "engine": "fake", "returncode": 0},
        )
        exported_pdf_path = None
        if output_pdf_path is not None:
            exported_pdf_path = self.artifact_store.export_pdf(key=key, output_path=output_pdf_path).output_path
        return SimpleNamespace(
            ok=True,
            errors=(),
            log_path=log_path,
            pdf_path=cached_pdf,
            exported_pdf_path=exported_pdf_path,
        )


class FailingCompilerBackend:
    def __init__(self, artifact_store) -> None:
        self.artifact_store = artifact_store

    def compile_render_model(self, *, render_model, template_spec, key, output_pdf_path=None, metadata=None):
        log_path = self.artifact_store.cache_compile_log(
            key=key,
            log_text="fake compile failed\n",
            metadata=metadata,
            compile_metadata={"ok": False, "engine": "fake", "returncode": 1, "errors": ["fake failure"]},
        )
        return SimpleNamespace(ok=False, errors=("fake failure",), log_path=log_path)


class GenerateCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_canonical_profile(ROOT / "templates" / "experiences.json")
        cls.experiences_path = ROOT / "templates" / "experiences.json"
        cls.resume_template_path = ROOT / "templates" / "resumes" / "jakes_resume_template.tex"

    def setUp(self) -> None:
        FakeCompilerBackend.calls = []

    def _valid_plan(self) -> dict:
        experience = self.profile.experiences[0]
        project = self.profile.projects[0]
        languages = self.profile.skill_groups_by_id()["languages"]
        return {
            "document_type": "resume",
            "template_id": "jakes_resume",
            "target": {"company": "Acme", "role": "Backend Engineer"},
            "sections": ["education", "experience", "projects", "technical_skills"],
            "education_ids": [self.profile.education[0].id],
            "experience_ids": [experience.id],
            "project_ids": [project.id],
            "bullet_ids_by_item": {
                experience.id: [experience.bullets[0].id],
                project.id: [project.bullets[0].id],
            },
            "skill_ids_by_group": {"languages": [languages.skills[0].id]},
            "rationale": "JSON_ONLY_SENTINEL",
        }

    def test_resume_mode_uses_json_planner_and_deterministic_outputs(self) -> None:
        prompts: list[str] = []

        def fake_call_gemini(prompt: str, api_key: str, *, model_id: str) -> str:
            prompts.append(prompt)
            return json.dumps(self._valid_plan())

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            with patch.object(generate_cli, "call_gemini", side_effect=fake_call_gemini):
                with redirect_stdout(io.StringIO()):
                    status = generate_cli.main(
                        [
                            "--mode",
                            "resume",
                            "--jd",
                            "Python backend engineer",
                            "--api-key",
                            "fake-key",
                            "--experiences",
                            str(self.experiences_path),
                            "--resume-template",
                            str(self.resume_template_path),
                            "--output-dir",
                            str(output_dir),
                            "--output-name",
                            "acme",
                        ],
                        compiler_backend_factory=FakeCompilerBackend,
                    )

            tex_path = output_dir / "acme_resume.tex"
            pdf_path = output_dir / "acme_resume.pdf"
            rendered_tex = tex_path.read_text(encoding="utf-8")

            self.assertEqual(status, 0)
            self.assertEqual(len(prompts), 1)
            self.assertIn("selection_plan_shape", prompts[0])
            self.assertIn(self.profile.experiences[0].id, prompts[0])
            self.assertNotIn("Generate a tailored LaTeX", prompts[0])
            self.assertNotIn("\\documentclass", prompts[0])
            self.assertNotIn("source_template", prompts[0])
            self.assertTrue(tex_path.is_file())
            self.assertTrue(pdf_path.is_file())
            self.assertIn("\\documentclass", rendered_tex)
            self.assertNotIn("JSON_ONLY_SENTINEL", rendered_tex)
            self.assertEqual(pdf_path.read_bytes(), b"%PDF-1.7\nfake compiled pdf\n")
            self.assertEqual(len(FakeCompilerBackend.calls), 1)

    def test_resume_mode_reuses_cached_pdf_without_second_backend_invocation(self) -> None:
        prompts: list[str] = []

        def fake_call_gemini(prompt: str, api_key: str, *, model_id: str) -> str:
            prompts.append(prompt)
            return json.dumps(self._valid_plan())

        def forbidden_backend(_artifact_store):
            raise AssertionError("cached PDF should be exported without constructing backend")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            argv = [
                "--mode",
                "resume",
                "--jd",
                "Python backend engineer",
                "--api-key",
                "fake-key",
                "--experiences",
                str(self.experiences_path),
                "--resume-template",
                str(self.resume_template_path),
                "--output-dir",
                str(output_dir),
                "--output-name",
                "cached",
            ]
            with patch.object(generate_cli, "call_gemini", side_effect=fake_call_gemini):
                with redirect_stdout(io.StringIO()):
                    first_status = generate_cli.main(argv, compiler_backend_factory=FakeCompilerBackend)

            with patch.object(generate_cli, "call_gemini", side_effect=AssertionError("planner cache should be hit")):
                with redirect_stdout(io.StringIO()) as stdout:
                    second_status = generate_cli.main(argv, compiler_backend_factory=forbidden_backend)
            second_stdout = stdout.getvalue()
            pdf_bytes = (output_dir / "cached_resume.pdf").read_bytes()

        self.assertEqual(first_status, 0)
        self.assertEqual(second_status, 0)
        self.assertEqual(len(prompts), 1)
        self.assertEqual(len(FakeCompilerBackend.calls), 1)
        self.assertEqual(pdf_bytes, b"%PDF-1.7\nfake compiled pdf\n")
        self.assertIn("Artifact cache hit", second_stdout)

    def test_resume_compile_failure_exports_tex_but_not_pdf_and_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            with patch.object(generate_cli, "call_gemini", return_value=json.dumps(self._valid_plan())):
                with redirect_stdout(io.StringIO()):
                    status = generate_cli.main(
                        [
                            "--mode",
                            "resume",
                            "--jd",
                            "Python backend engineer",
                            "--api-key",
                            "fake-key",
                            "--experiences",
                            str(self.experiences_path),
                            "--resume-template",
                            str(self.resume_template_path),
                            "--output-dir",
                            str(output_dir),
                            "--output-name",
                            "failed",
                        ],
                        compiler_backend_factory=FailingCompilerBackend,
                    )

            self.assertEqual(status, 1)
            self.assertTrue((output_dir / "failed_resume.tex").is_file())
            self.assertFalse((output_dir / "failed_resume.pdf").exists())

    def test_cover_letter_mode_fails_without_calling_gemini_or_writing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            with patch.object(generate_cli, "call_gemini", side_effect=AssertionError("should not call Gemini")):
                with redirect_stdout(io.StringIO()):
                    status = generate_cli.main(
                        [
                            "--mode",
                            "cover-letter",
                            "--jd",
                            "Cover letter role",
                            "--output-dir",
                            str(output_dir),
                            "--output-name",
                            "letter",
                        ]
                    )

            self.assertEqual(status, 1)
            self.assertFalse((output_dir / "letter_cover_letter.tex").exists())
            self.assertFalse((output_dir / "letter_cover_letter.pdf").exists())


if __name__ == "__main__":
    unittest.main()
