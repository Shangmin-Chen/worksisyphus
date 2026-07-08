from __future__ import annotations

import argparse
import ast
import contextlib
import dataclasses
import hashlib
import importlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from . import (
    ArtifactStore,
    CompilerBackend,
    GeminiPlanner,
    InvalidPdfArtifactError,
    PlanCache,
    PlanValidationError,
    RenderModel,
    Target,
    artifact_cache_key,
    atomic_write_bytes,
    build_render_model,
    canonical_profile_hash,
    deterministic_fallback_selection_plan,
    get_template_spec,
    load_canonical_profile,
    normalize_selection_plan,
    parse_planner_json,
    render_tex,
    selection_plan_artifact_json,
)
from .models import Contact
from .planner import validate_planner_plan_shape


CheckStatus = Literal["pass", "fail", "warn", "skip", "info"]

GRADE_LABELS = {
    "A": "prod ready",
    "B": "getting there",
    "C": "needs major fixes",
    "D": "ngmi",
    "F": "dog shit",
}


@dataclass(frozen=True)
class BenchmarkCheck:
    id: str
    category: str
    title: str
    max_points: float
    earned_points: float
    status: CheckStatus
    detail: str = ""

    def __post_init__(self) -> None:
        if self.max_points < 0:
            raise ValueError("max_points must be non-negative")
        if self.earned_points < 0:
            raise ValueError("earned_points must be non-negative")
        if self.earned_points > self.max_points:
            raise ValueError("earned_points cannot exceed max_points")

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class BenchmarkConfig:
    run_unit_tests: bool = True
    run_real_compile: bool = True
    unittest_min_count: int = 60
    unittest_timeout_seconds: float = 60.0
    real_compile_timeout_seconds: float = 45.0


@dataclass(frozen=True)
class BenchmarkReport:
    checks: tuple[BenchmarkCheck, ...]

    @property
    def max_score(self) -> float:
        return sum(check.max_points for check in self.checks)

    @property
    def score(self) -> float:
        return sum(check.earned_points for check in self.checks)

    @property
    def percent(self) -> float:
        if self.max_score == 0:
            return 0.0
        return self.score / self.max_score * 100

    @property
    def grade(self) -> str:
        return letter_grade(self.percent)

    @property
    def grade_label(self) -> str:
        return GRADE_LABELS[self.grade]

    def category_scores(self) -> dict[str, dict[str, float]]:
        categories: dict[str, dict[str, float]] = {}
        for check in self.checks:
            bucket = categories.setdefault(check.category, {"earned": 0.0, "max": 0.0})
            bucket["earned"] += check.earned_points
            bucket["max"] += check.max_points
        for values in categories.values():
            max_points = values["max"]
            values["percent"] = values["earned"] / max_points * 100 if max_points else 0.0
        return categories

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "max_score": round(self.max_score, 2),
            "percent": round(self.percent, 2),
            "grade": self.grade,
            "grade_label": self.grade_label,
            "category_scores": self.category_scores(),
            "checks": [check.as_dict() for check in self.checks],
        }


Probe = Callable[[Path, BenchmarkConfig], Iterable[BenchmarkCheck]]
PROBE_EXCEPTION_DEFAULT_POINTS = 25.0


def letter_grade(percent: float) -> str:
    if percent >= 95:
        return "A"
    if percent >= 80:
        return "B"
    if percent >= 65:
        return "C"
    if percent >= 50:
        return "D"
    return "F"


def run_benchmark(
    *,
    root: str | Path | None = None,
    config: BenchmarkConfig | None = None,
    probe_functions: Sequence[Probe] | None = None,
) -> BenchmarkReport:
    repo_root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    active_config = config or BenchmarkConfig()
    probes = tuple(probe_functions or DEFAULT_PROBES)
    checks: list[BenchmarkCheck] = []
    for probe in probes:
        try:
            checks.extend(probe(repo_root, active_config))
        except Exception as exc:
            points = _probe_expected_points(probe)
            checks.append(
                BenchmarkCheck(
                    id=f"benchmark.probe_error.{probe.__name__}",
                    category="benchmark",
                    title=f"Probe {probe.__name__} completed without crashing",
                    max_points=points,
                    earned_points=0,
                    status="fail",
                    detail=f"{exc.__class__.__name__}: {exc}",
                )
            )
    return BenchmarkReport(tuple(checks))


def format_human_report(report: BenchmarkReport) -> str:
    lines = [
        "worksisyphus deterministic compiler benchmark",
        (
            f"Score: {report.score:.1f}/{report.max_score:.1f} "
            f"({report.percent:.1f}%)"
        ),
        f"Grade: {report.grade} - {report.grade_label}",
        "",
        "Category scores:",
    ]
    for category, score in sorted(report.category_scores().items()):
        lines.append(
            f"- {category}: {score['earned']:.1f}/{score['max']:.1f} "
            f"({score['percent']:.1f}%)"
        )
    lines.append("")
    lines.append("Checks:")
    for check in report.checks:
        points = f"{check.earned_points:.1f}/{check.max_points:.1f}"
        line = f"[{check.status.upper()}] {points} {check.category} :: {check.title}"
        if check.detail:
            line += f" - {check.detail}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score the deterministic compiler against the production-readiness benchmark."
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip unittest discovery. The score will include an explicit failed tests check.",
    )
    parser.add_argument(
        "--skip-real-compile",
        action="store_true",
        help="Skip the optional real TeX engine smoke check.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root to benchmark.",
    )
    args = parser.parse_args(argv)
    report = run_benchmark(
        root=args.root,
        config=BenchmarkConfig(
            run_unit_tests=not args.skip_tests,
            run_real_compile=not args.skip_real_compile,
        ),
    )
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print(format_human_report(report), end="")
    return 0 if report.percent >= 80 else 1


def _probe_tests(root: Path, config: BenchmarkConfig) -> Iterable[BenchmarkCheck]:
    if not config.run_unit_tests:
        return [
            _check(
                "tests.unittest_discovery",
                "tests",
                "unittest discovery passes",
                16,
                False,
                "skipped by --skip-tests",
            ),
            _source_presence_check(root),
        ]

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    src_path = str(root / "src")
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=config.unittest_timeout_seconds,
        env=env,
        check=False,
    )
    output = completed.stdout + completed.stderr
    ran = _parse_unittest_count(output)
    if completed.returncode == 0 and ran >= config.unittest_min_count:
        unit_check = _pass(
            "tests.unittest_discovery",
            "tests",
            "unittest discovery passes",
            16,
            f"ran {ran} tests",
        )
    elif completed.returncode == 0:
        earned = min(15.0, 16.0 * ran / max(config.unittest_min_count, 1))
        unit_check = BenchmarkCheck(
            id="tests.unittest_discovery",
            category="tests",
            title="unittest discovery passes",
            max_points=16,
            earned_points=earned,
            status="warn",
            detail=f"ran {ran} tests; target is {config.unittest_min_count}",
        )
    else:
        unit_check = _fail(
            "tests.unittest_discovery",
            "tests",
            "unittest discovery passes",
            16,
            _tail(output),
        )
    return [unit_check, _source_presence_check(root)]


def _source_presence_check(root: Path) -> BenchmarkCheck:
    required = [
        root / "tests" / "test_renderer_resume.py",
        root / "tests" / "test_artifact_cache.py",
        root / "tests" / "test_compiler_backend.py",
        root / "tests" / "test_planner.py",
        root / "tests" / "test_slice5_migration.py",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    return _check(
        "tests.coverage_breadth",
        "tests",
        "determinism, cache, compiler, planner, and migration tests exist",
        4,
        not missing,
        "all expected focused test files are present" if not missing else "missing: " + ", ".join(missing),
    )


def _probe_determinism(root: Path, _config: BenchmarkConfig) -> Iterable[BenchmarkCheck]:
    api = _load_root_package_module(root, "worksisyphus")
    profile = api.load_canonical_profile(root / "templates" / "experiences.json")
    template = api.get_template_spec("jakes_resume")
    plan = api.deterministic_fallback_selection_plan(profile=profile, template_spec=template)
    render_model = api.build_render_model(profile=profile, selection_plan=plan, template_spec=template)
    first_tex = api.render_tex(render_model, template)
    second_tex = api.render_tex(render_model, template)
    expected_fragments = [
        r"\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}",
        r"%-----------EXPERIENCE-----------",
        r"\section{Experience}",
        r"\end{document}",
    ]
    stable = first_tex == second_tex and all(fragment in first_tex for fragment in expected_fragments)

    profile_hash = api.canonical_profile_hash(profile)
    first_key = api.artifact_cache_key(
        selection_plan=plan,
        template_spec=template,
        canonical_profile_hash_value=profile_hash,
    )
    same_key = api.artifact_cache_key(
        selection_plan=api.normalize_selection_plan(
            {**plan.artifact_dict(), "rationale": "different rationale"},
            profile=profile,
            template_spec=template,
        ),
        template_spec=template,
        canonical_profile_hash_value=profile_hash,
    )
    raw_plan = plan.artifact_dict()
    changed_plan = dict(raw_plan)
    changed_plan["sections"] = list(reversed(raw_plan["sections"]))
    changed_key = api.artifact_cache_key(
        selection_plan=api.normalize_selection_plan(changed_plan, profile=profile, template_spec=template),
        template_spec=template,
        canonical_profile_hash_value=profile_hash,
    )

    prompt_plan_cache_ok = _planner_cache_probe(api=api, profile=profile, template=template)
    cover_letter_ok, cover_letter_detail = _cover_letter_renderer_probe(api)

    return [
        _check(
            "determinism.renderer_snapshot",
            "determinism",
            "renderer emits stable fields and formatting from scratch",
            6,
            stable,
            "same render bytes and expected Jake-format commands" if stable else "render bytes or formatting changed",
        ),
        _check(
            "determinism.artifact_key",
            "determinism",
            "artifact key is stable, rationale-free, and order-sensitive",
            5,
            first_key == same_key and first_key != changed_key,
            "rationale ignored; section order changes key"
            if first_key == same_key and first_key != changed_key
            else "artifact key invariants failed",
        ),
        _cache_reuse_check(root),
        _check(
            "determinism.planner_cache",
            "determinism",
            "Gemini selection planning is JSON-only and cacheable",
            5,
            prompt_plan_cache_ok,
            "second identical planning request used cached SelectionPlan"
            if prompt_plan_cache_ok
            else "planner cache/shape validation probe failed",
        ),
        _check(
            "determinism.cover_letter_renderer",
            "determinism",
            "deterministic cover-letter renderer exists",
            4,
            cover_letter_ok,
            cover_letter_detail,
        ),
    ]


def _planner_cache_probe(*, api: Any, profile: Any, template: Any) -> bool:
    experience = profile.experiences[0]
    project = profile.projects[0]
    languages = profile.skill_groups_by_id()["languages"]
    raw_plan = {
        "document_type": "resume",
        "template_id": "jakes_resume",
        "target": {"company": "Acme", "role": "Backend Engineer"},
        "sections": list(template.section_order),
        "education_ids": [profile.education[0].id],
        "experience_ids": [experience.id],
        "project_ids": [project.id],
        "bullet_ids_by_item": {
            experience.id: [experience.bullets[0].id],
            project.id: [project.bullets[0].id],
        },
        "skill_ids_by_group": {"languages": [languages.skills[0].id]},
        "rationale": "first rationale",
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = api.PlanCache(Path(temp_dir) / "cache")
        calls: list[str] = []

        def model(_prompt: str) -> str:
            calls.append("called")
            return json.dumps(raw_plan)

        planner = api.GeminiPlanner(model, cache=cache, model_id="benchmark-gemini")
        first = planner.plan(raw_input="Python backend engineer", profile=profile, template_spec=template)
        second = api.GeminiPlanner(
            lambda _prompt: (_ for _ in ()).throw(RuntimeError("model should not be called")),
            cache=cache,
            model_id="benchmark-gemini",
        ).plan(raw_input="Python backend engineer", profile=profile, template_spec=template)
    return (
        len(calls) == 1
        and not first.from_cache
        and second.from_cache
        and second.plan.rationale == "first rationale"
    )


def _cover_letter_renderer_probe(api: Any) -> tuple[bool, str]:
    template = api.get_template_spec("default_cover_letter")
    render_model = api.RenderModel(
        document_type="cover_letter",
        template_id="default_cover_letter",
        contact=api.Contact(name="Benchmark"),
        target=api.Target(company="Acme", role="Engineer"),
        sections=template.section_order,
        education=(),
        experiences=(),
        projects=(),
        skills=(),
    )
    try:
        api.render_tex(render_model, template)
    except NotImplementedError:
        return False, "not implemented; supported paths fail closed instead"
    except Exception as exc:
        return False, f"{exc.__class__.__name__}: {exc}"
    return True, "cover-letter TemplateSpec renders through local compiler"


def _cache_reuse_check(root: Path) -> BenchmarkCheck:
    compile_cli = _load_root_module(root, "compile")
    calls: list[str] = []

    class FakeCompilerBackend:
        def __init__(self, artifact_store: ArtifactStore) -> None:
            self.artifact_store = artifact_store

        def compile_render_model(self, *, key: str, output_pdf_path: Path | None = None, metadata=None, **_kwargs):
            calls.append(key)
            source_pdf = self.artifact_store.cache_dir / "fake-build" / "resume.pdf"
            source_pdf.parent.mkdir(parents=True, exist_ok=True)
            source_pdf.write_bytes(b"%PDF-1.7\nbenchmark compiled pdf\n")
            cached_pdf = self.artifact_store.cache_pdf_from_path(
                key=key,
                pdf_path=source_pdf,
                metadata=metadata,
                compile_metadata={"ok": True, "engine": "benchmark", "returncode": 0},
            )
            exported_pdf_path = None
            if output_pdf_path is not None:
                exported_pdf_path = self.artifact_store.export_pdf(
                    key=key,
                    output_path=output_pdf_path,
                ).output_path
            return SimpleNamespace(
                ok=True,
                errors=(),
                log_path=None,
                pdf_path=cached_pdf,
                exported_pdf_path=exported_pdf_path,
            )

    def forbidden_backend(_artifact_store: ArtifactStore):
        raise AssertionError("cached PDF should be copied without recompiling")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            cache_dir = temp_root / "cache"
            first_pdf = temp_root / "first.pdf"
            second_pdf = temp_root / "second.pdf"
            compile_cli.compile_resume(
                root / "templates" / "experiences.json",
                temp_root / "first.tex",
                pdf_output=first_pdf,
                cache_dir=cache_dir,
                compiler_backend_factory=FakeCompilerBackend,
            )
            result = compile_cli.compile_resume(
                root / "templates" / "experiences.json",
                temp_root / "second.tex",
                pdf_output=second_pdf,
                cache_dir=cache_dir,
                compiler_backend_factory=forbidden_backend,
            )
            ok = (
                len(calls) == 1
                and result == second_pdf
                and second_pdf.read_bytes() == b"%PDF-1.7\nbenchmark compiled pdf\n"
            )
    except Exception as exc:
        return _fail(
            "determinism.artifact_cache_reuse",
            "determinism",
            "identical profile/template/plan copies cached PDF",
            5,
            f"{exc.__class__.__name__}: {exc}",
        )
    return _check(
        "determinism.artifact_cache_reuse",
        "determinism",
        "identical profile/template/plan copies cached PDF",
        5,
        ok,
        "second run did not construct compiler backend" if ok else "second run recompiled or exported wrong bytes",
    )


def _probe_safety(root: Path, _config: BenchmarkConfig) -> Iterable[BenchmarkCheck]:
    artifacts_source = _read_text(root / "src" / "worksisyphus" / "artifacts.py")
    compiler_source = _read_text(root / "src" / "worksisyphus" / "compiler.py")
    compile_source = _read_text(root / "src" / "compile.py")
    generate_source = _read_text(root / "src" / "generate.py")
    tui_source = _read_text(root / "src" / "tui.py")
    compile_sh = _read_text(root / "compile.sh")

    atomic_source_ok = all(token in artifacts_source for token in ("tempfile.mkstemp", "os.replace", "os.fsync"))
    atomic_behavior_ok, atomic_behavior_detail = _atomic_write_behavior_probe(root)
    atomic_ok = atomic_source_ok and atomic_behavior_ok
    compiler_ok = all(token in compiler_source for token in ("TemporaryDirectory", "shell=False", "cwd=build_dir"))
    tui_raw_ok, tui_raw_detail = _tui_no_raw_tex_source_audit(tui_source)
    no_raw_compile_ok = (
        "Generate a tailored LaTeX" not in generate_source
        and "\\documentclass" not in _planner_prompt_source(generate_source)
        and "tex_files/*.tex" not in compile_sh
        and "latexmk" not in compile_sh
        and "pdflatex" not in compile_sh
        and "latexmk" not in compile_source
        and "pdflatex" not in compile_source
        and tui_raw_ok
    )
    planner_ok = _planner_validation_probe(root)
    pdf_ok = _pdf_validation_probe(root)

    return [
        _check(
            "safety.atomic_writes",
            "safety",
            "artifact writes use temp files, fsync, and atomic replace",
            5,
            atomic_ok,
            "source and behavior probe preserve prior output on replace failure"
            if atomic_ok
            else f"source_ok={atomic_source_ok}; behavior={atomic_behavior_detail}",
        ),
        _check(
            "safety.compiler_isolation",
            "safety",
            "compiler runs in isolated temp dirs with shell-free argv",
            6,
            compiler_ok,
            "CompilerBackend uses TemporaryDirectory, cwd isolation, and shell=False"
            if compiler_ok
            else "compiler isolation/source probe failed",
        ),
        _check(
            "safety.no_raw_tex_compile",
            "safety",
            "raw or Gemini-authored TeX cannot reach executable compile paths",
            6,
            no_raw_compile_ok,
            f"source/AST smoke passed; {tui_raw_detail}"
            if no_raw_compile_ok
            else f"legacy raw/Gemini TeX compile surface found; {tui_raw_detail}",
        ),
        _check(
            "safety.planner_fail_closed",
            "safety",
            "planner rejects TeX/document commands and incomplete plan shapes",
            4,
            planner_ok,
            "TeX commands and partial plans are rejected before normalization"
            if planner_ok
            else "planner accepted unsafe or incomplete output",
        ),
        _check(
            "safety.pdf_validation",
            "safety",
            "PDF cache/export validates bytes before publishing",
            4,
            pdf_ok,
            "invalid cached bytes are rejected and prior exports are preserved"
            if pdf_ok
            else "invalid PDF cache behavior regressed",
        ),
    ]


def _planner_prompt_source(generate_source: str) -> str:
    return "\n".join(line for line in generate_source.splitlines() if "prompt" in line.lower())


def _tui_no_raw_tex_source_audit(tui_source: str) -> tuple[bool, str]:
    try:
        tree = ast.parse(tui_source)
    except SyntaxError as exc:
        return False, f"TUI AST parse failed: {exc.msg}"

    function_names = {
        node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    forbidden_functions = {"compile_single_tex", "selected_tex_files"}
    present_forbidden_functions = sorted(forbidden_functions & function_names)
    tex_globs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "glob"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "TEX_DIR"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "*.tex"
    ]
    engine_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.value in {"latexmk", "pdflatex"}
    }
    ok = (
        "RAW_IMPORT_DIR" in tui_source
        and "format_raw_import_filename" in function_names
        and not present_forbidden_functions
        and not tex_globs
        and not engine_literals
    )
    if ok:
        return True, "TUI AST has raw import helper and no TeX glob/engine compile function"
    details: list[str] = []
    if "RAW_IMPORT_DIR" not in tui_source:
        details.append("RAW_IMPORT_DIR missing")
    if "format_raw_import_filename" not in function_names:
        details.append("format_raw_import_filename missing")
    if present_forbidden_functions:
        details.append("forbidden functions: " + ", ".join(present_forbidden_functions))
    if tex_globs:
        details.append("TEX glob calls found")
    if engine_literals:
        details.append("engine literals found: " + ", ".join(sorted(engine_literals)))
    return False, "; ".join(details)


def _planner_validation_probe(root: Path) -> bool:
    api, planner_module = _load_root_package_modules(root, "worksisyphus", "worksisyphus.planner")
    profile = api.load_canonical_profile(root / "templates" / "experiences.json")
    template = api.get_template_spec("jakes_resume")
    try:
        api.parse_planner_json(r"\documentclass{article}\begin{document}unsafe\end{document}")
    except Exception:
        tex_rejected = True
    else:
        tex_rejected = False

    partial_plan = {
        "document_type": "resume",
        "template_id": "jakes_resume",
        "sections": list(template.section_order),
    }
    try:
        planner_module.validate_planner_plan_shape(partial_plan, profile=profile, template_spec=template)
    except api.PlanValidationError:
        partial_rejected = True
    else:
        partial_rejected = False
    return tex_rejected and partial_rejected


def _atomic_write_behavior_probe(root: Path) -> tuple[bool, str]:
    artifacts_module = _load_root_package_module(root, "worksisyphus.artifacts")
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "resume.tex"
        output.write_text("previous output\n", encoding="utf-8")

        original_replace = artifacts_module.os.replace

        def failing_replace(_source, _target):
            raise RuntimeError("replace failed")

        artifacts_module.os.replace = failing_replace
        try:
            try:
                artifacts_module.atomic_write_text(output, "new partial output\n")
            except RuntimeError:
                pass
            else:
                return False, "atomic_write_text did not surface replace failure"
        finally:
            artifacts_module.os.replace = original_replace

        if output.read_text(encoding="utf-8") != "previous output\n":
            return False, "previous output was overwritten on failed replace"
        if list(output.parent.glob(f".{output.name}.*.tmp")):
            return False, "temporary file was left behind on failed replace"
    return True, "prior output preserved and temp file cleaned up"


def _pdf_validation_probe(root: Path) -> bool:
    api = _load_root_package_module(root, "worksisyphus")
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = api.ArtifactStore(root / "cache")
        key = "benchmark-invalid-pdf"
        output = root / "export.pdf"
        output.write_bytes(b"%PDF-1.7\nprior export\n")
        store.artifact_dir(key).mkdir(parents=True)
        store.pdf_path(key).write_bytes(b"not a pdf\n")
        try:
            store.export_pdf(key=key, output_path=output)
        except api.InvalidPdfArtifactError:
            return output.read_bytes() == b"%PDF-1.7\nprior export\n"
    return False


def _probe_compile(root: Path, config: BenchmarkConfig) -> Iterable[BenchmarkCheck]:
    compile_cli = _load_root_module(root, "compile")
    checks: list[BenchmarkCheck] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        tex_output = temp_root / "resume.tex"
        try:
            result = compile_cli.compile_resume(
                root / "templates" / "experiences.json",
                tex_output,
                compile_pdf=False,
                cache_dir=temp_root / "cache",
                compiler_backend_factory=lambda _store: (_ for _ in ()).throw(
                    AssertionError("tex-only should not compile")
                ),
            )
            tex_ok = result == tex_output and tex_output.read_text(encoding="utf-8").startswith("\\documentclass")
        except Exception as exc:
            tex_ok = False
            tex_detail = f"{exc.__class__.__name__}: {exc}"
        else:
            tex_detail = "tex-only rebuild exported deterministic TeX in a temp dir"
        checks.append(
            _check(
                "compile.tex_only",
                "compile",
                "compile.py can export deterministic TeX without a compiler",
                5,
                tex_ok,
                tex_detail,
            )
        )

    safe_backend_ok, safe_backend_detail = _safe_backend_compile_probe(root)
    checks.append(
        _check(
            "compile.safe_backend",
            "compile",
            "CompilerBackend publishes valid PDFs through the artifact store",
            5,
            safe_backend_ok,
            safe_backend_detail,
        )
    )

    custom_output_ok, custom_output_detail = _custom_output_probe(root, compile_cli)
    checks.append(
        _check(
            "compile.custom_output",
            "compile",
            "custom CLI TeX output defaults the PDF next to that TeX",
            5,
            custom_output_ok,
            custom_output_detail,
        )
    )

    checks.append(_real_compile_smoke(root, config))
    return checks


def _safe_backend_compile_probe(root: Path) -> tuple[bool, str]:
    api = _load_root_package_module(root, "worksisyphus")
    profile = api.load_canonical_profile(root / "templates" / "experiences.json")
    template = api.get_template_spec("jakes_resume")
    plan = api.deterministic_fallback_selection_plan(profile=profile, template_spec=template)
    render_model = api.build_render_model(profile=profile, selection_plan=plan, template_spec=template)
    seen: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args, **kwargs):
        seen.append((args, kwargs))
        build_dir = Path(kwargs["cwd"])
        (build_dir / "artifact.log").write_text("", encoding="utf-8")
        (build_dir / "artifact.pdf").write_bytes(b"%PDF-1.7\nbenchmark backend pdf\n")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = api.ArtifactStore(root / "cache")
        key = "benchmark-safe-backend"
        backend = api.CompilerBackend(
            store,
            runner=fake_run,
            find_executable=lambda name: f"/usr/bin/{name}" if name == "latexmk" else None,
        )
        result = backend.compile_render_model(
            render_model=render_model,
            template_spec=template,
            key=key,
            output_pdf_path=root / "resume.pdf",
        )
        shell_false = bool(seen and seen[0][1].get("shell") is False and isinstance(seen[0][0], list))
        ok = result.ok and (root / "resume.pdf").read_bytes().startswith(b"%PDF-") and shell_false
    return ok, "fake engine produced a cached/exported PDF with list argv and shell=False" if ok else "safe backend probe failed"


def _custom_output_probe(root: Path, compile_cli: Any) -> tuple[bool, str]:
    calls: list[Path | None] = []

    class FakeCompilerBackend:
        def __init__(self, artifact_store: ArtifactStore) -> None:
            self.artifact_store = artifact_store

        def compile_render_model(self, *, key: str, output_pdf_path: Path | None = None, metadata=None, **_kwargs):
            calls.append(output_pdf_path)
            source_pdf = self.artifact_store.cache_dir / "fake-build" / "resume.pdf"
            source_pdf.parent.mkdir(parents=True, exist_ok=True)
            source_pdf.write_bytes(b"%PDF-1.7\nbenchmark custom output pdf\n")
            cached_pdf = self.artifact_store.cache_pdf_from_path(
                key=key,
                pdf_path=source_pdf,
                metadata=metadata,
                compile_metadata={"ok": True, "engine": "benchmark", "returncode": 0},
            )
            exported_pdf_path = None
            if output_pdf_path is not None:
                exported_pdf_path = self.artifact_store.export_pdf(key=key, output_path=output_pdf_path).output_path
            return SimpleNamespace(ok=True, errors=(), log_path=None, pdf_path=cached_pdf, exported_pdf_path=exported_pdf_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        output_tex = temp_root / "custom.tex"
        expected_pdf = temp_root / "custom.pdf"
        with contextlib.redirect_stdout(io.StringIO()):
            status = compile_cli.main(
                [
                    "--resume",
                    str(root / "templates" / "experiences.json"),
                    "--output",
                    str(output_tex),
                    "--cache-dir",
                    str(temp_root / "cache"),
                ],
                compiler_backend_factory=FakeCompilerBackend,
            )
        ok = status == 0 and expected_pdf.is_file() and calls == [expected_pdf]
    return ok, "PDF defaulted to <custom>.pdf" if ok else "custom --output would not publish next to TeX"


def _real_compile_smoke(root: Path, config: BenchmarkConfig) -> BenchmarkCheck:
    if not config.run_real_compile:
        return BenchmarkCheck(
            id="compile.real_tex_engine_smoke",
            category="compile",
            title="optional real TeX engine smoke",
            max_points=0,
            earned_points=0,
            status="skip",
            detail="skipped by --skip-real-compile",
        )
    if shutil.which("latexmk") is None and shutil.which("pdflatex") is None:
        return BenchmarkCheck(
            id="compile.real_tex_engine_smoke",
            category="compile",
            title="optional real TeX engine smoke",
            max_points=0,
            earned_points=0,
            status="skip",
            detail="latexmk/pdflatex not available",
        )
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "src" / "compile.py"),
                "--resume",
                str(root / "templates" / "experiences.json"),
                "--output",
                str(temp_root / "resume.tex"),
                "--pdf-output",
                str(temp_root / "resume.pdf"),
                "--cache-dir",
                str(temp_root / "cache"),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=config.real_compile_timeout_seconds,
            check=False,
        )
        pdf_ok = (temp_root / "resume.pdf").is_file() and (temp_root / "resume.pdf").read_bytes().startswith(b"%PDF-")
    status: CheckStatus = "pass" if completed.returncode == 0 and pdf_ok else "fail"
    detail = "real TeX engine produced a PDF in a temp dir" if status == "pass" else _tail(completed.stdout + completed.stderr)
    return BenchmarkCheck(
        id="compile.real_tex_engine_smoke",
        category="compile",
        title="optional real TeX engine smoke",
        max_points=0,
        earned_points=0,
        status=status,
        detail=detail,
    )


def _probe_tui_tooling(root: Path, _config: BenchmarkConfig) -> Iterable[BenchmarkCheck]:
    tui_source = _read_text(root / "src" / "tui.py")
    readme = _read_text(root / "README.md")
    benchmark_doc = _read_text(root / "docs" / "benchmark.md")
    nonblocking_ok, nonblocking_detail = _tui_worker_source_audit(tui_source)
    no_arbitrary_tex_ok, no_arbitrary_tex_detail = _tui_no_raw_tex_source_audit(tui_source)
    fail_closed_ok, fail_closed_detail = _cover_letter_fail_closed_probe(root)
    runtime_ok, runtime_detail = _tui_runtime_probe(root)
    docs_ok = (
        "python src/benchmark.py" in readme
        and "Grade scale" in benchmark_doc
        and "Gemini does not write final TeX" in benchmark_doc
    )
    return [
        _check(
            "tui.nonblocking",
            "tui_tooling",
            "TUI routes blocking generate/compile work through workers",
            3,
            nonblocking_ok,
            nonblocking_detail
            if nonblocking_ok
            else f"blocking command routing source probe failed: {nonblocking_detail}",
        ),
        _check(
            "tui.no_arbitrary_tex_compile",
            "tui_tooling",
            "TUI imports raw TeX as non-compileable input and compiles only trusted artifacts",
            4,
            no_arbitrary_tex_ok,
            no_arbitrary_tex_detail
            if no_arbitrary_tex_ok
            else f"TUI raw compile surface found: {no_arbitrary_tex_detail}",
        ),
        _check(
            "tui.fail_closed_unsupported",
            "tui_tooling",
            "unsupported cover-letter path fails closed",
            3,
            fail_closed_ok,
            fail_closed_detail,
        ),
        _check(
            "tui.runtime_smoke",
            "tui_tooling",
            "TUI runtime import/instantiation smoke passes when dependencies are present",
            3,
            runtime_ok,
            runtime_detail,
        ),
        _check(
            "tui.docs",
            "tui_tooling",
            "README and benchmark docs describe the current safe workflow",
            2,
            docs_ok,
            "README points to benchmark docs and docs state Gemini/TeX boundary"
            if docs_ok
            else "benchmark or safety docs are missing/stale",
        ),
    ]


def _tui_worker_source_audit(tui_source: str) -> tuple[bool, str]:
    try:
        tree = ast.parse(tui_source)
    except SyntaxError as exc:
        return False, f"TUI AST parse failed: {exc.msg}"

    has_thread_worker = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run_worker"
        and any(
            keyword.arg == "thread"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        )
        for node in ast.walk(tree)
    )
    has_popen = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Popen"
        for node in ast.walk(tree)
    )
    ok = has_thread_worker and has_popen
    detail = "AST/source smoke: subprocess work is launched from a Textual thread worker"
    if not ok:
        missing = []
        if not has_thread_worker:
            missing.append("run_worker(thread=True)")
        if not has_popen:
            missing.append("subprocess.Popen")
        detail = "missing " + ", ".join(missing)
    return ok, detail


def _cover_letter_fail_closed_probe(root: Path) -> tuple[bool, str]:
    generate_cli = _load_root_module(root, "generate")
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "out"
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
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
        ok = (
            status == 1
            and "not implemented yet" in stdout.getvalue()
            and not (output_dir / "letter_cover_letter.tex").exists()
            and not (output_dir / "letter_cover_letter.pdf").exists()
        )
    return ok, "cover-letter mode returns nonzero without writing artifacts" if ok else "cover-letter path did not fail closed"


def _tui_runtime_probe(root: Path) -> tuple[bool, str]:
    if importlib.util.find_spec("textual") is None:
        return False, "Textual is not installed, so runtime smoke is not covered"
    try:
        tui_module = _load_root_module(root, "tui")
        app = tui_module.ResumeTUI()
        filename = tui_module.format_raw_import_filename("foo.tex", "resume")
    except Exception as exc:
        return False, f"{exc.__class__.__name__}: {exc}"
    ok = getattr(app, "TITLE", "") == "worksisyphus" and filename == "foo_resume.raw.txt"
    return ok, "Textual import and app construction succeeded" if ok else "Textual smoke returned unexpected values"


def _load_root_module(root: Path, module_name: str) -> Any:
    module_path = root / "src" / f"{module_name}.py"
    if not module_path.is_file():
        raise FileNotFoundError(f"Target module does not exist: {module_path}")

    unique_name = _unique_root_module_name(root, module_name)
    with _target_src_import_context(root):
        spec = importlib.util.spec_from_file_location(unique_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load import spec for {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[unique_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(unique_name, None)
            raise
        return module


def _load_root_package_module(root: Path, dotted_name: str) -> Any:
    return _load_root_package_modules(root, dotted_name)[0]


def _load_root_package_modules(root: Path, *dotted_names: str) -> tuple[Any, ...]:
    with _target_src_import_context(root):
        return tuple(importlib.import_module(name) for name in dotted_names)


@contextlib.contextmanager
def _target_src_import_context(root: Path):
    src_path = str((root / "src").resolve())
    original_path = list(sys.path)
    saved_modules = {
        name: module
        for name, module in sys.modules.items()
        if _is_target_package_name(name)
    }
    for name in list(saved_modules):
        sys.modules.pop(name, None)

    sys.path[:] = [src_path] + [path for path in original_path if path != src_path]
    try:
        yield
    finally:
        for name in [
            module_name
            for module_name in sys.modules
            if _is_target_package_name(module_name)
        ]:
            sys.modules.pop(name, None)
        sys.modules.update(saved_modules)
        sys.path[:] = original_path


def _is_target_package_name(module_name: str) -> bool:
    return module_name == "worksisyphus" or module_name.startswith("worksisyphus.")


def _unique_root_module_name(root: Path, module_name: str) -> str:
    digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:12]
    return f"_worksisyphus_benchmark_{module_name}_{digest}"


def _probe_expected_points(probe: Probe) -> float:
    explicit = getattr(probe, "expected_points", None)
    if explicit is not None:
        return float(explicit)
    return _DEFAULT_PROBE_POINTS_BY_NAME.get(
        getattr(probe, "__name__", ""),
        PROBE_EXCEPTION_DEFAULT_POINTS,
    )


def _check(
    check_id: str,
    category: str,
    title: str,
    points: float,
    passed: bool,
    detail: str = "",
) -> BenchmarkCheck:
    return _pass(check_id, category, title, points, detail) if passed else _fail(check_id, category, title, points, detail)


def _pass(check_id: str, category: str, title: str, points: float, detail: str = "") -> BenchmarkCheck:
    return BenchmarkCheck(
        id=check_id,
        category=category,
        title=title,
        max_points=points,
        earned_points=points,
        status="pass",
        detail=detail,
    )


def _fail(check_id: str, category: str, title: str, points: float, detail: str = "") -> BenchmarkCheck:
    return BenchmarkCheck(
        id=check_id,
        category=category,
        title=title,
        max_points=points,
        earned_points=0,
        status="fail",
        detail=detail,
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _parse_unittest_count(output: str) -> int:
    match = re.search(r"Ran\s+(\d+)\s+tests?", output)
    return int(match.group(1)) if match else 0


def _tail(text: str, *, lines: int = 8) -> str:
    stripped = text.strip()
    if not stripped:
        return "no output"
    return " | ".join(stripped.splitlines()[-lines:])


DEFAULT_PROBES: tuple[Probe, ...] = (
    _probe_tests,
    _probe_determinism,
    _probe_safety,
    _probe_compile,
    _probe_tui_tooling,
)

_DEFAULT_PROBE_POINTS_BY_NAME = {
    "_probe_tests": 20.0,
    "_probe_determinism": 25.0,
    "_probe_safety": 25.0,
    "_probe_compile": 15.0,
    "_probe_tui_tooling": 15.0,
}
