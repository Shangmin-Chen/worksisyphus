"""worksisyphus: Simon Chen's deterministic resume compiler."""
from .compiler import CompileError, CompileResult, compile_tex
from .pipeline import build_canonical, tailor
from .planner import PlanError, parse_plan, plan_selection, sanitize_name
from .profile import Profile, load_profile, planner_index
from .renderer import render_resume
from .selection import Pick, Selection, full_selection, trim_step

__all__ = [
    "CompileError",
    "CompileResult",
    "Pick",
    "PlanError",
    "Profile",
    "Selection",
    "build_canonical",
    "compile_tex",
    "full_selection",
    "load_profile",
    "parse_plan",
    "plan_selection",
    "planner_index",
    "render_resume",
    "sanitize_name",
    "tailor",
    "trim_step",
]
