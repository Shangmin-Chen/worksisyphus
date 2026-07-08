from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus.benchmark import (
    BenchmarkCheck,
    BenchmarkConfig,
    BenchmarkReport,
    format_human_report,
    letter_grade,
    run_benchmark,
    _load_root_module,
    _tui_no_raw_tex_source_audit,
)


class BenchmarkScoringTests(unittest.TestCase):
    def test_letter_grade_thresholds_match_user_scale(self) -> None:
        cases = [
            (100, "A"),
            (95, "A"),
            (94.99, "B"),
            (80, "B"),
            (79.99, "C"),
            (65, "C"),
            (64.99, "D"),
            (50, "D"),
            (49.99, "F"),
        ]

        for percent, expected in cases:
            with self.subTest(percent=percent):
                self.assertEqual(letter_grade(percent), expected)

    def test_report_scores_categories_and_json(self) -> None:
        report = BenchmarkReport(
            (
                BenchmarkCheck(
                    id="tests.pass",
                    category="tests",
                    title="tests pass",
                    max_points=20,
                    earned_points=20,
                    status="pass",
                ),
                BenchmarkCheck(
                    id="determinism.partial",
                    category="determinism",
                    title="some deterministic paths",
                    max_points=10,
                    earned_points=5,
                    status="warn",
                    detail="representative partial",
                ),
                BenchmarkCheck(
                    id="compile.info",
                    category="compile",
                    title="optional compile smoke",
                    max_points=0,
                    earned_points=0,
                    status="skip",
                    detail="not scored",
                ),
            )
        )

        data = report.as_dict()

        self.assertEqual(report.score, 25)
        self.assertEqual(report.max_score, 30)
        self.assertEqual(report.grade, "B")
        self.assertEqual(data["category_scores"]["tests"]["earned"], 20)
        self.assertEqual(data["category_scores"]["determinism"]["max"], 10)
        self.assertEqual(data["checks"][2]["status"], "skip")
        json.dumps(data)

    def test_run_benchmark_accepts_monkeypatched_probes(self) -> None:
        calls: list[tuple[Path, BenchmarkConfig]] = []

        def fake_tests(root: Path, config: BenchmarkConfig):
            calls.append((root, config))
            return [
                BenchmarkCheck(
                    id="tests.fake",
                    category="tests",
                    title="fake tests",
                    max_points=20,
                    earned_points=20,
                    status="pass",
                    detail="patched",
                )
            ]

        def fake_tui(root: Path, config: BenchmarkConfig):
            calls.append((root, config))
            return [
                BenchmarkCheck(
                    id="tui.fake",
                    category="tui_tooling",
                    title="fake tui",
                    max_points=15,
                    earned_points=12,
                    status="warn",
                    detail="patched",
                )
            ]

        config = BenchmarkConfig(run_unit_tests=False, run_real_compile=False)
        report = run_benchmark(
            root=ROOT,
            config=config,
            probe_functions=(fake_tests, fake_tui),
        )
        human = format_human_report(report)

        self.assertEqual(len(calls), 2)
        self.assertTrue(all(call[0] == ROOT for call in calls))
        self.assertTrue(all(call[1] is config for call in calls))
        self.assertEqual(report.score, 32)
        self.assertEqual(report.max_score, 35)
        self.assertEqual(report.grade, "B")
        self.assertIn("worksisyphus deterministic compiler benchmark", human)
        self.assertIn("Grade: B - getting there", human)
        self.assertIn("[WARN] 12.0/15.0 tui_tooling :: fake tui - patched", human)

    def test_probe_exceptions_are_reported_without_crashing_report(self) -> None:
        def exploding_probe(_root: Path, _config: BenchmarkConfig):
            raise RuntimeError("boom")

        exploding_probe.expected_points = 12

        report = run_benchmark(
            root=ROOT,
            config=BenchmarkConfig(run_unit_tests=False, run_real_compile=False),
            probe_functions=(exploding_probe,),
        )

        self.assertEqual(report.max_score, 12)
        self.assertEqual(report.score, 0)
        self.assertEqual(report.grade, "F")
        self.assertEqual(report.checks[0].status, "fail")
        self.assertIn("RuntimeError: boom", report.checks[0].detail)

    def test_root_module_loader_uses_target_worksisyphus_package(self) -> None:
        import worksisyphus

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package_dir = root / "src" / "worksisyphus"
            package_dir.mkdir(parents=True)
            (package_dir / "__init__.py").write_text(
                "SENTINEL = 'target-root-package'\n",
                encoding="utf-8",
            )
            (root / "src" / "compile.py").write_text(
                "from worksisyphus import SENTINEL\n",
                encoding="utf-8",
            )

            module = _load_root_module(root, "compile")

        self.assertEqual(module.SENTINEL, "target-root-package")
        self.assertFalse(hasattr(worksisyphus, "SENTINEL"))

    def test_tui_raw_tex_audit_allows_template_globs_but_rejects_output_globs(self) -> None:
        safe_source = """
from pathlib import Path
RAW_IMPORT_DIR = Path("raw_inputs/tex_imports")
def format_raw_import_filename(name, template_type):
    return "safe.raw.txt"
def template_options(directory):
    return sorted(directory.glob("*.tex"))
"""
        unsafe_source = safe_source + """
TEX_DIR = Path("tex_files")
def selected_tex_files():
    return sorted(TEX_DIR.glob("*.tex"))
"""

        safe_ok, safe_detail = _tui_no_raw_tex_source_audit(safe_source)
        unsafe_ok, unsafe_detail = _tui_no_raw_tex_source_audit(unsafe_source)

        self.assertTrue(safe_ok, safe_detail)
        self.assertFalse(unsafe_ok)
        self.assertIn("forbidden functions", unsafe_detail)
        self.assertIn("TEX glob calls found", unsafe_detail)


if __name__ == "__main__":
    unittest.main()
