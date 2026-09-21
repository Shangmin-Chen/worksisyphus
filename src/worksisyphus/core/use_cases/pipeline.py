"""Core Use Cases: Canonical rebuild and plan-driven one-page resume tailoring."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from ...adapters.outbound.filesystem.profile_loader import load_profile as _default_load_profile
from ...adapters.outbound.latex.compiler import compile_tex as _default_compile_tex
from ...ports.compiler import CompileResult, CompilerPort
from ..domain.models import DEFAULT_PROFILE_PATH, Profile, Selection
from ..domain.plan import parse_plan
from ..domain.rules import TrimCut, full_selection, trim_step
from ..rendering.latex import render_resume

TEX_DIR = Path("tex_files")
PREVIEW_DIR = TEX_DIR
PAGE_LIMIT = 1
OVERFULL_TOLERANCE_PT = 2.0

_OVERFULL_WIDTH_RE = re.compile(r"^([\d.]+)pt too wide")

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
    selection = full_selection(profile)
    log("Rendering canonical resume...")
    active_compiler = compiler or _get_default_compiler()
    result = active_compiler.compile_tex(render_resume(profile, selection), selection.name, TEX_DIR, TEX_DIR)
    if result.overfull:
        log("Warning: horizontal overflow: " + "; ".join(result.overfull))
    log(f"Exported {result.pdf_path} ({result.pages} page{'s' if result.pages != 1 else ''}).")
    return result


def tailor(
    plan_text: str,
    profile: Profile | None = None,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    plan_name: str = "custom",
    log: Log = _silent,
    tex_dir: Path = TEX_DIR,
    pdf_dir: Path = PREVIEW_DIR,
    compiler: CompilerPort | None = None,
) -> CompileResult:
    """Render the plan and trim deterministically until it fits one page."""
    if not plan_text.strip():
        raise ValueError("Plan is empty.")
    active_profile = profile if profile is not None else load_profile(profile_path)

    initial_selection = parse_plan(plan_text, active_profile)
    log(f"Plan parsed; output name: {initial_selection.name}")
    pdf_dir.mkdir(parents=True, exist_ok=True)

    active_compiler = compiler or _get_default_compiler()
    selection: Selection | None = initial_selection
    cuts: list[TrimCut] = []
    while selection is not None:
        result = active_compiler.compile_tex(render_resume(active_profile, selection), selection.name, tex_dir, pdf_dir)
        if result.pages <= PAGE_LIMIT:
            excessive_overfull = tuple(
                entry
                for entry in result.overfull
                if (match := _OVERFULL_WIDTH_RE.match(entry)) and float(match.group(1)) > OVERFULL_TOLERANCE_PT
            )
            if excessive_overfull:
                raise RuntimeError("Horizontal overflow detected: " + "; ".join(excessive_overfull))
            log(f"Exported {result.pdf_path} ({result.pages} page).")
            return replace(result, trimmed=tuple(cuts))
        log(f"{result.pages} pages; trimming and recompiling...")
        step = trim_step(selection)
        if step is None:
            break
        selection, cut = step
        cuts.append(cut)
        log(cut.log_line())

    raise RuntimeError("Could not fit the resume on one page even after maximum trimming.")


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
