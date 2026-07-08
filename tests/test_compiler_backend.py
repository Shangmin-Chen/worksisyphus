from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus import (
    ArtifactStore,
    CompilerBackend,
    build_render_model,
    get_template_spec,
    normalize_selection_plan,
)
from worksisyphus.profile import parse_canonical_profile


PDF_BYTES = b"%PDF-1.7\nmock pdf\n"


def build_minimal_render_model():
    profile = parse_canonical_profile({"contact": {"name": "Ada Lovelace"}})
    template = get_template_spec("jakes_resume")
    plan = normalize_selection_plan(
        {
            "document_type": "resume",
            "template_id": "jakes_resume",
            "sections": [],
        },
        profile=profile,
        template_spec=template,
    )
    return build_render_model(profile=profile, selection_plan=plan, template_spec=template), template


class CompilerBackendTests(unittest.TestCase):
    def test_mocked_success_publishes_pdf_log_and_metadata(self) -> None:
        render_model, template = build_minimal_render_model()
        calls: list[tuple[list[str], dict[str, Any]]] = []

        def fake_run(args, **kwargs):
            calls.append((args, kwargs))
            build_dir = Path(kwargs["cwd"])
            (build_dir / "artifact.log").write_text("LaTeX Warning: mocked warning\n", encoding="utf-8")
            (build_dir / "artifact.pdf").write_bytes(PDF_BYTES)
            return subprocess.CompletedProcess(args, 0, stdout="latexmk stdout", stderr="")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = ArtifactStore(root / "cache")
            backend = CompilerBackend(
                store,
                timeout_seconds=5,
                runner=fake_run,
                find_executable=lambda name: f"/usr/bin/{name}" if name == "latexmk" else None,
            )

            result = backend.compile_render_model(
                render_model=render_model,
                template_spec=template,
                key="success-key",
                output_pdf_path=root / "exports" / "resume.pdf",
                metadata={"job": "success"},
            )
            metadata = store.read_metadata("success-key")

            self.assertTrue(result.ok)
            self.assertEqual(result.engine, "latexmk")
            self.assertEqual(result.returncode, 0)
            self.assertFalse(result.timed_out)
            self.assertEqual(result.pdf_path.read_bytes(), PDF_BYTES)
            self.assertEqual(result.exported_pdf_path.read_bytes(), PDF_BYTES)
            self.assertIn("LaTeX Warning: mocked warning", result.warnings)
            self.assertIn("latexmk stdout", result.stdout)
            self.assertTrue(result.log_path.is_file())
            self.assertTrue(metadata["has_pdf"])
            self.assertTrue(metadata["has_log"])
            self.assertEqual(metadata["pdf_status"], "compiled")
            self.assertTrue(metadata["last_compile"]["ok"])
            self.assertEqual(metadata["last_compile"]["engine"], "latexmk")

    def test_mocked_failure_preserves_prior_cached_and_exported_pdf(self) -> None:
        render_model, template = build_minimal_render_model()
        calls: list[str] = []

        def fake_run(args, **kwargs):
            calls.append(Path(args[0]).name)
            build_dir = Path(kwargs["cwd"])
            (build_dir / "artifact.log").write_text("! Undefined control sequence.\n", encoding="utf-8")
            return subprocess.CompletedProcess(args, 1, stdout="failed stdout", stderr="failed stderr")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            key = "failure-key"
            store = ArtifactStore(root / "cache")
            old_pdf = root / "old.pdf"
            old_pdf.write_bytes(b"%PDF-1.7\nold cached pdf\n")
            export_pdf = root / "exports" / "resume.pdf"
            export_pdf.parent.mkdir()
            export_pdf.write_bytes(b"%PDF-1.7\nold exported pdf\n")
            store.cache_tex(key=key, tex="old tex\n")
            store.cache_pdf_from_path(
                key=key,
                pdf_path=old_pdf,
                compile_metadata={"ok": True, "engine": "pdflatex"},
            )
            prior_cached_bytes = store.pdf_path(key).read_bytes()
            prior_exported_bytes = export_pdf.read_bytes()

            backend = CompilerBackend(
                store,
                timeout_seconds=5,
                runner=fake_run,
                find_executable=lambda name: f"/usr/bin/{name}",
            )

            result = backend.compile_render_model(
                render_model=render_model,
                template_spec=template,
                key=key,
                output_pdf_path=export_pdf,
            )
            metadata = store.read_metadata(key)

            self.assertFalse(result.ok)
            self.assertIsNone(result.pdf_path)
            self.assertEqual(result.attempted_engines, ("latexmk", "pdflatex"))
            self.assertEqual(calls, ["latexmk", "pdflatex"])
            self.assertEqual(store.pdf_path(key).read_bytes(), prior_cached_bytes)
            self.assertEqual(export_pdf.read_bytes(), prior_exported_bytes)
            self.assertTrue(metadata["has_pdf"])
            self.assertEqual(metadata["pdf_status"], "compile_failed_existing_pdf_preserved")
            self.assertFalse(metadata["last_compile"]["ok"])
            self.assertIn("Undefined control sequence", "\n".join(result.errors))

    def test_timeout_returns_timed_out_non_ok_result(self) -> None:
        render_model, template = build_minimal_render_model()

        def fake_run(args, **kwargs):
            raise subprocess.TimeoutExpired(
                cmd=args,
                timeout=kwargs["timeout"],
                output="partial stdout",
                stderr="partial stderr",
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtifactStore(Path(temp_dir) / "cache")
            backend = CompilerBackend(
                store,
                timeout_seconds=1,
                runner=fake_run,
                find_executable=lambda name: f"/usr/bin/{name}" if name == "latexmk" else None,
            )

            result = backend.compile_render_model(
                render_model=render_model,
                template_spec=template,
                key="timeout-key",
            )
            metadata = store.read_metadata("timeout-key")

            self.assertFalse(result.ok)
            self.assertTrue(result.timed_out)
            self.assertIsNone(result.returncode)
            self.assertEqual(result.stdout, "partial stdout")
            self.assertEqual(result.stderr, "partial stderr")
            self.assertEqual(metadata["pdf_status"], "compile_timeout")
            self.assertFalse(metadata["has_pdf"])

    def test_no_engine_available_returns_structured_failure_and_cached_log(self) -> None:
        render_model, template = build_minimal_render_model()

        def fake_run(args, **kwargs):
            self.fail("runner should not be called when no engine is available")

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtifactStore(Path(temp_dir) / "cache")
            backend = CompilerBackend(
                store,
                runner=fake_run,
                find_executable=lambda name: None,
            )

            result = backend.compile_render_model(
                render_model=render_model,
                template_spec=template,
                key="no-engine-key",
            )
            metadata = store.read_metadata("no-engine-key")

            self.assertFalse(result.ok)
            self.assertEqual(result.attempted_engines, ())
            self.assertEqual(result.engine, "")
            self.assertTrue(result.log_path.is_file())
            self.assertIn("No configured TeX engine is available.", result.errors)
            self.assertIn("latexmk is unavailable; skipped.", result.warnings)
            self.assertEqual(metadata["pdf_status"], "compile_failed")
            self.assertFalse(metadata["has_pdf"])
            self.assertTrue(metadata["has_log"])

    def test_success_returncode_without_valid_pdf_returns_failure_without_cached_pdf(self) -> None:
        render_model, template = build_minimal_render_model()

        cases = [
            ("missing", None, "did not produce"),
            ("empty", b"", "empty PDF"),
            ("non_pdf", b"not a pdf\n", "not a PDF"),
        ]

        for name, pdf_bytes, expected_error in cases:
            with self.subTest(name=name):
                def fake_run(args, **kwargs):
                    build_dir = Path(kwargs["cwd"])
                    (build_dir / "artifact.log").write_text("", encoding="utf-8")
                    if pdf_bytes is not None:
                        (build_dir / "artifact.pdf").write_bytes(pdf_bytes)
                    return subprocess.CompletedProcess(args, 0, stdout=f"{name} stdout", stderr="")

                with tempfile.TemporaryDirectory() as temp_dir:
                    store = ArtifactStore(Path(temp_dir) / "cache")
                    backend = CompilerBackend(
                        store,
                        engines=("latexmk",),
                        runner=fake_run,
                        find_executable=lambda engine: f"/usr/bin/{engine}",
                    )

                    result = backend.compile_render_model(
                        render_model=render_model,
                        template_spec=template,
                        key=f"invalid-output-{name}",
                    )
                    metadata = store.read_metadata(f"invalid-output-{name}")

                    self.assertFalse(result.ok)
                    self.assertIsNone(result.pdf_path)
                    self.assertFalse(store.pdf_path(f"invalid-output-{name}").exists())
                    self.assertIn(expected_error, "\n".join(result.errors))
                    self.assertEqual(metadata["pdf_status"], "compile_failed")
                    self.assertFalse(metadata["has_pdf"])

    def test_stale_executable_oserror_tries_fallback_and_reports_success(self) -> None:
        render_model, template = build_minimal_render_model()
        calls: list[str] = []

        def fake_run(args, **kwargs):
            engine = Path(args[0]).name
            calls.append(engine)
            if engine == "latexmk":
                raise OSError("stale executable")
            build_dir = Path(kwargs["cwd"])
            (build_dir / "artifact.log").write_text("", encoding="utf-8")
            (build_dir / "artifact.pdf").write_bytes(PDF_BYTES)
            return subprocess.CompletedProcess(args, 0, stdout="fallback stdout", stderr="")

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtifactStore(Path(temp_dir) / "cache")
            backend = CompilerBackend(
                store,
                runner=fake_run,
                find_executable=lambda name: f"/usr/bin/{name}",
            )

            result = backend.compile_render_model(
                render_model=render_model,
                template_spec=template,
                key="oserror-fallback-key",
            )
            metadata = store.read_metadata("oserror-fallback-key")

            self.assertTrue(result.ok)
            self.assertEqual(calls, ["latexmk", "pdflatex"])
            self.assertEqual(result.attempted_engines, ("latexmk", "pdflatex"))
            self.assertEqual(result.engine, "pdflatex")
            self.assertIn("OSError: stale executable", result.stderr)
            self.assertIn("latexmk execution failed", result.log_text)
            self.assertIn("latexmk failed; trying pdflatex fallback.", result.warnings)
            self.assertEqual(result.pdf_path.read_bytes(), PDF_BYTES)
            self.assertTrue(metadata["last_compile"]["ok"])
            self.assertEqual(metadata["last_compile"]["engine"], "pdflatex")

    def test_oserror_without_successful_fallback_returns_structured_failure(self) -> None:
        render_model, template = build_minimal_render_model()

        def fake_run(args, **kwargs):
            raise OSError("permission denied")

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtifactStore(Path(temp_dir) / "cache")
            backend = CompilerBackend(
                store,
                engines=("latexmk",),
                runner=fake_run,
                find_executable=lambda name: f"/usr/bin/{name}",
            )

            result = backend.compile_render_model(
                render_model=render_model,
                template_spec=template,
                key="oserror-failure-key",
            )
            metadata = store.read_metadata("oserror-failure-key")

            self.assertFalse(result.ok)
            self.assertIsNone(result.returncode)
            self.assertFalse(result.timed_out)
            self.assertIn("OSError: permission denied", result.stderr)
            self.assertIn("latexmk execution failed", "\n".join(result.errors))
            self.assertTrue(result.log_path.is_file())
            self.assertEqual(metadata["pdf_status"], "compile_failed")
            self.assertFalse(metadata["has_pdf"])

    def test_argv_uses_list_subprocess_and_shell_false(self) -> None:
        render_model, template = build_minimal_render_model()
        seen_args: list[list[str]] = []
        seen_kwargs: list[dict[str, Any]] = []

        def fake_run(args, **kwargs):
            seen_args.append(args)
            seen_kwargs.append(kwargs)
            build_dir = Path(kwargs["cwd"])
            (build_dir / "artifact.log").write_text("", encoding="utf-8")
            (build_dir / "artifact.pdf").write_bytes(PDF_BYTES)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtifactStore(Path(temp_dir) / "cache")
            backend = CompilerBackend(
                store,
                runner=fake_run,
                find_executable=lambda name: f"/usr/bin/{name}" if name == "latexmk" else None,
            )

            result = backend.compile_render_model(
                render_model=render_model,
                template_spec=template,
                key="argv-key",
            )

            self.assertTrue(result.ok)
            self.assertIsInstance(seen_args[0], list)
            self.assertEqual(seen_args[0][0], "/usr/bin/latexmk")
            self.assertFalse(seen_kwargs[0]["shell"])
            self.assertEqual(seen_kwargs[0]["cwd"].name.startswith("worksisyphus-compile-"), True)


if __name__ == "__main__":
    unittest.main()
