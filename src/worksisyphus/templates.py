from __future__ import annotations

from .models import TemplateSpec
from .profile import normalize_id


BUILTIN_TEMPLATE_SPECS: dict[str, TemplateSpec] = {
    "jakes_resume": TemplateSpec(
        id="jakes_resume",
        version="1",
        document_type="resume",
        source_template="templates/resumes/jakes_resume_template.tex",
        section_order=("education", "experience", "projects", "technical_skills"),
        max_education=2,
        max_experiences=3,
        max_projects=2,
        max_bullets_per_experience=3,
        max_bullets_per_project=4,
        max_skills_per_group=12,
        skill_group_order=(
            "languages",
            "frameworks_and_libraries",
            "databases_and_infrastructure",
            "platforms_and_systems",
        ),
        page_limit=1,
        preamble="jakes_resume_article",
        command_profile="jakes_resume_commands",
        spacing_profile="compact_one_page",
    ),
    "default_cover_letter": TemplateSpec(
        id="default_cover_letter",
        version="1",
        document_type="cover_letter",
        source_template="templates/cover_letters/default_cover_letter.tex",
        section_order=("letter_body", "supporting_bullets"),
        max_education=1,
        max_experiences=3,
        max_projects=3,
        max_bullets_per_experience=3,
        max_bullets_per_project=3,
        max_skills_per_group=8,
        skill_group_order=(
            "languages",
            "frameworks_and_libraries",
            "databases_and_infrastructure",
            "platforms_and_systems",
        ),
        page_limit=1,
        preamble="cover_letter_article",
        command_profile="cover_letter_commands",
        spacing_profile="letter_single_page",
    ),
}


def get_template_spec(template_id: str) -> TemplateSpec:
    normalized_id = normalize_id(template_id)
    try:
        return BUILTIN_TEMPLATE_SPECS[normalized_id]
    except KeyError as exc:
        known = ", ".join(sorted(BUILTIN_TEMPLATE_SPECS))
        raise KeyError(f"Unknown template spec {template_id!r}; known template specs: {known}") from exc
