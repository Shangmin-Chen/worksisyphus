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
    plan_name: str = "custom",
    force: bool = False,
    log: Log = _silent,
    tex_dir: Path = TEX_DIR,
    pdf_dir: Path = PDF_DIR,
) -> CompileResult:
    """Render the plan and trim deterministically until it fits one page."""
    if not plan_text.strip():
        raise ValueError("Plan is empty.")
    profile = load_profile(profile_path)
    initial_selection = parse_plan(plan_text, profile)
    log(f"Plan parsed; output name: {initial_selection.name}")
    normalized_plan = plan_text.replace("\r\n", "\n").replace("\r", "\n")
    plan_hash = hashlib.sha256(normalized_plan.encode("utf-8")).hexdigest()

    pdf_dir.mkdir(parents=True, exist_ok=True)
    lock_path = pdf_dir / ".tailor.lock"
    if lock_path.is_file():
        try:
            lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
        except Exception:
            lock_data = {}

        if isinstance(lock_data, dict):
            locked_plan_name = lock_data.get("plan_name", "previous_plan")
            locked_plan_hash = lock_data.get("plan_hash", "")
            locked_at = lock_data.get("tailored_at", "")

            if locked_plan_hash and locked_plan_hash != plan_hash:
                if not force:
                    msg = f"Unarchived tailored resume exists for plan '{locked_plan_name}'"
                    if locked_at:
                        msg += f" (tailored at {locked_at})"
                    msg += ". Run `worksisyphus archive` first, or pass `--force` to overwrite."
                    raise RuntimeError(msg)
                log(f"Warning: Overwriting unarchived tailored resume for '{locked_plan_name}' (--force enabled).")

    provenance_path = pdf_dir / ".provenance.json"
    _write_provenance(provenance_path, {"plan_hash": plan_hash})

    selection: Selection | None = initial_selection
    while selection is not None:
        result = compile_tex(render_resume(profile, selection), selection.name, tex_dir, pdf_dir)
        if result.pages <= PAGE_LIMIT:
            excessive_overfull = tuple(
                entry
                for entry in result.overfull
                if (match := _OVERFULL_WIDTH_RE.match(entry)) and float(match.group(1)) > OVERFULL_TOLERANCE_PT
            )
            if excessive_overfull:
                raise RuntimeError("Horizontal overflow detected: " + "; ".join(excessive_overfull))
            log(f"Exported {result.pdf_path} ({result.pages} page).")
            pdf_hash = hashlib.sha256(result.pdf_path.read_bytes()).hexdigest()
            _write_provenance(provenance_path, {"plan_hash": plan_hash, "pdf_hash": pdf_hash})

            from datetime import UTC, datetime

            now_iso = datetime.now(UTC).isoformat()
            lock_info = {
                "plan_name": plan_name,
                "plan_hash": plan_hash,
                "pdf_hash": pdf_hash,
                "tailored_at": now_iso,
            }
            _write_provenance(lock_path, lock_info)
            return result
        log(f"{result.pages} pages; trimming and recompiling...")
        selection = trim_step(selection)

    raise RuntimeError("Could not fit the resume on one page even after maximum trimming.")


def _write_provenance(path: Path, data: dict[str, str]) -> None:
    """Atomically replace the build marker or lock file, avoiding a partially-written valid record."""
    temporary_path = path.with_name(f"{path.name}.tmp")
    temporary_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)
