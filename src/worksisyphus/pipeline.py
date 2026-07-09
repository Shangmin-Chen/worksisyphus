"""End-to-end flows: canonical rebuild and JD-tailored one-page resume."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .compiler import CompileResult, compile_tex
from .planner import CallModel, plan_selection
from .profile import DEFAULT_PROFILE_PATH, load_profile
from .renderer import render_resume
from .selection import Selection, full_selection, trim_step

TEX_DIR = Path("tex_files")
PDF_DIR = Path("resumes")
PAGE_LIMIT = 1

Log = Callable[[str], None]


def _silent(_: str) -> None:
    pass


def build_canonical(profile_path: Path = DEFAULT_PROFILE_PATH, log: Log = _silent) -> CompileResult:
    """Rebuild the full everything-included resume; no page limit applies."""
    profile = load_profile(profile_path)
    selection = full_selection(profile)
    log("Rendering canonical resume...")
    result = compile_tex(render_resume(profile, selection), selection.name, TEX_DIR, PDF_DIR)
    log(f"Exported {result.pdf_path} ({result.pages} page{'s' if result.pages != 1 else ''}).")
    return result


def tailor(
    jd_text: str,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    call_model: CallModel | None = None,
    log: Log = _silent,
) -> CompileResult:
    """Plan with Gemini, render locally, and trim deterministically until it fits one page."""
    if not jd_text.strip():
        raise ValueError("Job description is empty.")
    profile = load_profile(profile_path)
    log("Asking Gemini for a selection plan...")
    selection: Selection | None = plan_selection(jd_text, profile, call_model)
    log(f"Plan received; output name: {selection.name}")

    while selection is not None:
        result = compile_tex(render_resume(profile, selection), selection.name, TEX_DIR, PDF_DIR)
        if result.pages <= PAGE_LIMIT:
            log(f"Exported {result.pdf_path} ({result.pages} page).")
            return result
        log(f"{result.pages} pages; trimming and recompiling...")
        selection = trim_step(selection)

    raise RuntimeError("Could not fit the resume on one page even after maximum trimming.")
