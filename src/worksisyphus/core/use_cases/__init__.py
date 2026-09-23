"""Core application use cases orchestrating domain models, rules, and ports."""

from .application import (
    APPLICATIONS_DIR,
    STATUSES,
    ContactCrossCheck,
    apply,
    cross_check_contact_against_db,
    evaluate_application,
    list_applications,
    match_application_identifier,
    parse_app_folder,
    resolve_application_folder,
    slugify,
    sorted_application_names,
    update_application_status,
)
from .evaluator import (
    COMMON_TECH_TERMS,
    EvaluationReport,
    evaluate_pdf_against_jd,
    evaluate_resume_text,
    format_evaluation_report,
    selection_to_plain_text,
)
from .gates import check_resume_gates, run_resume_gates
from .optimizer import OptimizerError, optimize_plan, score_bullet
from .pipeline import PAGE_LIMIT, PREVIEW_DIR, TEX_DIR, build_canonical, tailor

__all__ = [
    "APPLICATIONS_DIR",
    "COMMON_TECH_TERMS",
    "PAGE_LIMIT",
    "PREVIEW_DIR",
    "STATUSES",
    "TEX_DIR",
    "ContactCrossCheck",
    "EvaluationReport",
    "OptimizerError",
    "apply",
    "build_canonical",
    "check_resume_gates",
    "cross_check_contact_against_db",
    "evaluate_application",
    "evaluate_pdf_against_jd",
    "evaluate_resume_text",
    "format_evaluation_report",
    "list_applications",
    "match_application_identifier",
    "optimize_plan",
    "parse_app_folder",
    "resolve_application_folder",
    "run_resume_gates",
    "score_bullet",
    "selection_to_plain_text",
    "slugify",
    "sorted_application_names",
    "tailor",
    "update_application_status",
]
