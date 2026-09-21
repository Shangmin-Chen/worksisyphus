"""Core Use Cases: Canonical rebuild and plan-driven one-page resume tailoring."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from ...adapters.outbound.filesystem.profile_loader import load_profile as _default_load_profile
from ...adapters.outbound.latex.compiler import compile_tex as _default_compile_tex
from ...ports.compiler import CompileResult, CompilerPort
from ..domain.gates import check_profile_gates
from ..domain.models import DEFAULT_PROFILE_PATH, Profile, Selection
from ..domain.plan import parse_plan
from ..domain.rules import TrimCut, full_selection, trim_step
from ..rendering.latex import render_resume

TEX_DIR = Path("tex_files")
PREVIEW_DIR = TEX_DIR
PAGE_LIMIT = 1
OVERFULL_TOLERANCE_PT = 2.0

Log = Callable[[str], None]

# Module-level defaults for compile_tex and load_profile so monkeypatching and direct use work
compile_tex = _default_compile_tex
load_profile = _default_load_profile


def _silent(_: str) -> None:
    pass


class _ModuleCompiler(CompilerPort):
    def compile_tex(self, tex: str, name: str, tex_dir: Path, pdf_dir: Path) -> CompileResult:
        return compile_tex(tex, name, tex_dir, pdf_dir)


def _get_default_compiler() -> CompilerPort:
    return _ModuleCompiler()


def build_canonical(
    profile_path: Path = DEFAULT_PROFILE_PATH,
    log: Log = _silent,
    compiler: CompilerPort | None = None,
) -> CompileResult:
    """Rebuild the full everything-included resume; no page limit applies."""
    profile = load_profile(profile_path)
    profile_gates = check_profile_gates(profile)
    failed_profile = [g for g in profile_gates if not g.passed]
    if failed_profile:
        raise RuntimeError(
            "Profile policy gate failed: "
            + "; ".join(f"{g.gate_name}: {', '.join(g.diagnostics)}" for g in failed_profile)
        )
    selection = full_selection(profile)
    log("Rendering canonical resume...")
    active_compiler = compiler or _get_default_compiler()
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    result = active_compiler.compile_tex(render_resume(profile, selection), selection.name, TEX_DIR, TEX_DIR)
    final_pdf = TEX_DIR / f"{selection.name}.pdf"
    if result.pdf_path.resolve() != final_pdf.resolve():
        shutil.copyfile(result.pdf_path, final_pdf)
        result.pdf_path.unlink(missing_ok=True)
    if result.overfull:
        log("Warning: horizontal overflow: " + "; ".join(str(entry) for entry in result.overfull))
    log(f"Exported {final_pdf} ({result.pages} page{'s' if result.pages != 1 else ''}).")
    return replace(result, pdf_path=final_pdf)


def tailor(
    plan_text: str,
    profile: Profile | None = None,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    log: Log = _silent,
    tex_dir: Path = TEX_DIR,
    pdf_dir: Path = PREVIEW_DIR,
    compiler: CompilerPort | None = None,
) -> CompileResult:
    """Render the plan and trim deterministically until it fits one page."""
    if not plan_text.strip():
        raise ValueError("Plan is empty.")
    active_profile = profile if profile is not None else load_profile(profile_path)
    profile_gates = check_profile_gates(active_profile)
    failed_profile = [g for g in profile_gates if not g.passed]
    if failed_profile:
        raise RuntimeError(
            "Profile policy gate failed: "
            + "; ".join(f"{g.gate_name}: {', '.join(g.diagnostics)}" for g in failed_profile)
        )

    initial_selection = parse_plan(plan_text, active_profile)

    log(f"Plan parsed; output name: {initial_selection.name}")
    pdf_dir.mkdir(parents=True, exist_ok=True)

    active_compiler = compiler or _get_default_compiler()
    selection: Selection | None = initial_selection
    cuts: list[TrimCut] = []
    final_pdf = pdf_dir / f"{initial_selection.name}.pdf"
    staged_pdfs: list[Path] = []

    try:
        while selection is not None:
            result = active_compiler.compile_tex(
                render_resume(active_profile, selection),
                selection.name,
                tex_dir,
                pdf_dir,
            )
            if result.pdf_path.resolve() != final_pdf.resolve():
                staged_pdfs.append(result.pdf_path)

            if result.pages <= PAGE_LIMIT:
                excessive_overfull = tuple(
                    entry for entry in result.overfull if entry.exceeds_tolerance(OVERFULL_TOLERANCE_PT)
                )
                if excessive_overfull:
                    raise RuntimeError(
                        "Horizontal overflow detected: " + "; ".join(str(entry) for entry in excessive_overfull)
                    )
                if result.pdf_path.resolve() != final_pdf.resolve():
                    shutil.copyfile(result.pdf_path, final_pdf)
                    result.pdf_path.unlink(missing_ok=True)
                    if result.pdf_path in staged_pdfs:
                        staged_pdfs.remove(result.pdf_path)
                log(f"Exported {final_pdf} ({result.pages} page).")
                return replace(result, pdf_path=final_pdf, trimmed=tuple(cuts))

            log(f"{result.pages} pages; trimming and recompiling...")
            if result.pdf_path.is_file() and result.pdf_path.resolve() != final_pdf.resolve():
                result.pdf_path.unlink(missing_ok=True)
                if result.pdf_path in staged_pdfs:
                    staged_pdfs.remove(result.pdf_path)

            step = trim_step(selection)
            if step is None:
                break
            selection, cut = step
            cuts.append(cut)
            log(cut.log_line())

        raise RuntimeError("Could not fit the resume on one page even after maximum trimming.")
    except Exception:
        for p in staged_pdfs:
            if p.is_file():
                p.unlink(missing_ok=True)
        final_pdf.unlink(missing_ok=True)
        raise


__all__ = [
    "PAGE_LIMIT",
    "PREVIEW_DIR",
    "TEX_DIR",
    "CompileResult",
    "build_canonical",
    "compile_tex",
    "load_profile",
    "tailor",
]
