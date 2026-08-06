"""End-to-end flows: canonical rebuild and plan-driven one-page resume."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path

from .compiler import CompileResult, compile_tex
from .plan import parse_plan
from .profile import DEFAULT_PROFILE_PATH, load_profile
from .renderer import render_resume
from .selection import Selection, full_selection, trim_step

TEX_DIR = Path("tex_files")
PDF_DIR = Path("resumes")
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
    result = compile_tex(render_resume(profile, selection), selection.name, TEX_DIR, PDF_DIR)
    if result.overfull:
        log("Warning: horizontal overflow: " + "; ".join(result.overfull))
    log(f"Exported {result.pdf_path} ({result.pages} page{'s' if result.pages != 1 else ''}).")
    return result


def tailor(
    plan_text: str,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    log: Log = _silent,
) -> CompileResult:
    """Render the plan and trim deterministically until it fits one page."""
    if not plan_text.strip():
        raise ValueError("Plan is empty.")
    profile = load_profile(profile_path)
    selection: Selection | None = parse_plan(plan_text, profile)
    log(f"Plan parsed; output name: {selection.name}")

    while selection is not None:
        result = compile_tex(render_resume(profile, selection), selection.name, TEX_DIR, PDF_DIR)
        if result.pages <= PAGE_LIMIT:
            excessive_overfull = tuple(
                entry
                for entry in result.overfull
                if (match := _OVERFULL_WIDTH_RE.match(entry))
                and float(match.group(1)) > OVERFULL_TOLERANCE_PT
            )
            if excessive_overfull:
                raise RuntimeError(
                    "Horizontal overflow detected: " + "; ".join(excessive_overfull)
                )
            log(f"Exported {result.pdf_path} ({result.pages} page).")
            plan_hash = hashlib.sha256(plan_text.encode("utf-8")).hexdigest()
            (PDF_DIR / ".provenance.json").write_text(json.dumps({"plan_hash": plan_hash}) + "\n", encoding="utf-8")
            return result
        log(f"{result.pages} pages; trimming and recompiling...")
        selection = trim_step(selection)

    raise RuntimeError("Could not fit the resume on one page even after maximum trimming.")
