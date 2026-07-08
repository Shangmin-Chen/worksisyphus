from __future__ import annotations

import ast
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import compile as compile_cli


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


class Slice5MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeCompilerBackend.calls = []

    def test_compile_sh_delegates_without_globbing_or_tex_engines(self) -> None:
        script = (ROOT / "compile.sh").read_text(encoding="utf-8")

        self.assertIn("src/compile.py", script)
        self.assertIn("--pdf-output", script)
        self.assertNotIn("tex_files/*.tex", script)
        self.assertNotIn("latexmk", script)
        self.assertNotIn("pdflatex", script)

    def test_tui_has_no_raw_tex_compile_path(self) -> None:
        source = (ROOT / "src" / "tui.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function_names = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }

        self.assertNotIn("compile_single_tex", function_names)
        self.assertNotIn("selected_tex_files", function_names)
        self.assertNotIn("latexmk", source)
        self.assertNotIn("pdflatex", source)
        self.assertNotIn('TEX_DIR.glob("*.tex")', source)
        self.assertNotIn("Save to tex_files", source)
        self.assertIn("RAW_IMPORT_DIR", source)
        self.assertIn("format_raw_import_filename", source)
        self.assertIn("atomic_write_text", source)

    def test_compile_py_has_no_legacy_renderer_or_direct_subprocess(self) -> None:
        source = (ROOT / "src" / "compile.py").read_text(encoding="utf-8")

        self.assertNotIn("import subprocess", source)
        self.assertNotIn("subprocess.run", source)
        self.assertNotIn("generate_latex_resume", source)
        self.assertNotIn("def tex_escape", source)
        self.assertNotIn("latexmk", source)
        self.assertNotIn("pdflatex", source)
        self.assertIn("deterministic_fallback_selection_plan", source)
        self.assertIn("CompilerBackend", source)

    def test_compile_py_tex_only_exports_deterministic_tex_without_compiler(self) -> None:
        def forbidden_compiler(_artifact_store):
            raise AssertionError("tex-only must not construct a compiler backend")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_tex = Path(temp_dir) / "resume.tex"
            result = compile_cli.compile_resume(
                ROOT / "templates" / "experiences.json",
                output_tex,
                compile_pdf=False,
                compiler_backend_factory=forbidden_compiler,
            )

            rendered_tex = output_tex.read_text(encoding="utf-8")

        self.assertEqual(result, output_tex)
        self.assertIn("\\documentclass", rendered_tex)
        self.assertIn("\\newcommand{\\resumeSubItem}[1]{\\resumeItem{#1}\\vspace{-4pt}}", rendered_tex)
        self.assertNotIn("\\newcommand{\\resumeSubItem}[1]{\\resumeSubItem{#1}", rendered_tex)

    def test_compile_py_compile_path_uses_injected_safe_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_tex = root / "resume.tex"
            output_pdf = root / "resume.pdf"
            result = compile_cli.compile_resume(
                ROOT / "templates" / "experiences.json",
                output_tex,
                pdf_output=output_pdf,
                cache_dir=root / "cache",
                compiler_backend_factory=FakeCompilerBackend,
            )

            rendered_tex = output_tex.read_text(encoding="utf-8")
            exported_pdf = output_pdf.read_bytes()

            self.assertEqual(result, output_pdf)
            self.assertEqual(exported_pdf, b"%PDF-1.7\nfake compiled pdf\n")
            self.assertIn("\\documentclass", rendered_tex)
            self.assertEqual(len(FakeCompilerBackend.calls), 1)
            self.assertEqual(FakeCompilerBackend.calls[0]["output_pdf_path"], output_pdf)
            self.assertEqual(FakeCompilerBackend.calls[0]["template_spec"].id, "jakes_resume")

    def test_compile_py_reuses_cached_pdf_without_second_backend_invocation(self) -> None:
        def forbidden_compiler(_artifact_store):
            raise AssertionError("cached PDF should be exported without constructing backend")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cache_dir = root / "cache"
            first_pdf = root / "first.pdf"
            second_pdf = root / "second.pdf"
            compile_cli.compile_resume(
                ROOT / "templates" / "experiences.json",
                root / "first.tex",
                pdf_output=first_pdf,
                cache_dir=cache_dir,
                compiler_backend_factory=FakeCompilerBackend,
            )
            self.assertEqual(len(FakeCompilerBackend.calls), 1)

            result = compile_cli.compile_resume(
                ROOT / "templates" / "experiences.json",
                root / "second.tex",
                pdf_output=second_pdf,
                cache_dir=cache_dir,
                compiler_backend_factory=forbidden_compiler,
            )
            second_pdf_bytes = second_pdf.read_bytes()

        self.assertEqual(result, second_pdf)
        self.assertEqual(second_pdf_bytes, b"%PDF-1.7\nfake compiled pdf\n")
        self.assertEqual(len(FakeCompilerBackend.calls), 1)

    def test_compile_py_custom_output_defaults_pdf_next_to_tex(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_tex = root / "custom.tex"
            output_pdf = root / "custom.pdf"
            with redirect_stdout(io.StringIO()):
                status = compile_cli.main(
                    [
                        "--resume",
                        str(ROOT / "templates" / "experiences.json"),
                        "--output",
                        str(output_tex),
                        "--cache-dir",
                        str(root / "cache"),
                    ],
                    compiler_backend_factory=FakeCompilerBackend,
                )
            pdf_exists = output_pdf.is_file()

        self.assertEqual(status, 0)
        self.assertTrue(pdf_exists)
        self.assertEqual(FakeCompilerBackend.calls[0]["output_pdf_path"], output_pdf)

    def test_compile_py_main_tex_only_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_tex = Path(temp_dir) / "resume.tex"
            with redirect_stdout(io.StringIO()) as stdout:
                status = compile_cli.main(
                    [
                        "--resume",
                        str(ROOT / "templates" / "experiences.json"),
                        "--output",
                        str(output_tex),
                        "--tex-only",
                    ],
                    compiler_backend_factory=FakeCompilerBackend,
                )
            tex_exists = output_tex.is_file()
            stdout_text = stdout.getvalue()

        self.assertEqual(status, 0)
        self.assertTrue(tex_exists)
        self.assertIn("Deterministic LaTeX source exported", stdout_text)


if __name__ == "__main__":
    unittest.main()
