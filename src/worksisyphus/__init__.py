"""worksisyphus: Simon Chen's deterministic resume compiler."""

from .application import apply, list_applications, update_application_status
from .compiler import CompileError, CompileResult, compile_tex
from .pipeline import build_canonical, tailor
from .plan import PlanError, parse_plan
from .profile import Profile, load_profile, profile_index, validate_contact
from .renderer import render_resume
from .selection import Pick, Selection, full_selection, trim_step

__all__ = [
    "CompileError",
    "CompileResult",
    "Pick",
    "PlanError",
    "Profile",
    "Selection",
    "apply",
    "build_canonical",
    "compile_tex",
    "full_selection",
    "list_applications",
    "load_profile",
    "parse_plan",
    "profile_index",
    "render_resume",
    "tailor",
    "trim_step",
    "update_application_status",
    "validate_contact",
]
