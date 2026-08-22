"""End-to-end flows: canonical rebuild and plan-driven one-page resume."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from .compiler import CompileResult, compile_tex
from .plan import parse_plan
from .profile import DEFAULT_PROFILE_PATH, Profile, load_profile
from .renderer import render_resume
from .selection import Selection, full_selection, trim_step

TEX_DIR = Path("tex_files")
# Delivered resumes live only in applications/<date>_<stem>/, written there by apply().
# Everything else this module produces is regenerable build output: the canonical database
# view and tailor()'s preview builds both land in TEX_DIR, which is gitignored.
PREVIEW_DIR = TEX_DIR
PAGE_LIMIT = 1
OVERFULL_TOLERANCE_PT = 2.0

_OVERFULL_WIDTH_RE = re.compile(r"^([\d.]+)pt too wide")

Log = Callable[[str], None]


def _silent(_: str) -> None:
    pass


def build_canonical(profile_path: Path = DEFAULT_PROFILE_PATH, log: Log = _silent) -> CompileResult:
    """Rebuild the full everything-included resume; no page limit applies."""
    profile = load_profile(profile_path)
    selection = full_selection(profile)
    log("Rendering canonical resume...")
    result = compile_tex(render_resume(profile, selection), selection.name, TEX_DIR, TEX_DIR)
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
) -> CompileResult:
    """Render the plan and trim deterministically until it fits one page.

    Writes to PREVIEW_DIR unless the caller names a destination; apply() passes its own
    staging directory so a delivered resume is only ever published through that path.
    """
    if not plan_text.strip():
        raise ValueError("Plan is empty.")
    active_profile = profile if profile is not None else load_profile(profile_path)
    initial_selection = parse_plan(plan_text, active_profile)
    log(f"Plan parsed; output name: {initial_selection.name}")
    pdf_dir.mkdir(parents=True, exist_ok=True)

    selection: Selection | None = initial_selection
    while selection is not None:
        result = compile_tex(render_resume(active_profile, selection), selection.name, tex_dir, pdf_dir)
        if result.pages <= PAGE_LIMIT:
            excessive_overfull = tuple(
                entry
                for entry in result.overfull
                if (match := _OVERFULL_WIDTH_RE.match(entry)) and float(match.group(1)) > OVERFULL_TOLERANCE_PT
            )
            if excessive_overfull:
                raise RuntimeError("Horizontal overflow detected: " + "; ".join(excessive_overfull))
            log(f"Exported {result.pdf_path} ({result.pages} page).")
            return result
        log(f"{result.pages} pages; trimming and recompiling...")
        selection = trim_step(selection)

    raise RuntimeError("Could not fit the resume on one page even after maximum trimming.")
