from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from .models import (
    CanonicalProfile,
    RenderExperience,
    RenderModel,
    RenderProject,
    SelectionPlan,
    SkillGroup,
    SkillItem,
    Target,
    TemplateSpec,
    ValidationErrorDetail,
)
from .profile import normalize_id


class PlanValidationError(ValueError):
    def __init__(self, errors: Iterable[ValidationErrorDetail]) -> None:
        self.errors = tuple(errors)
        message = "; ".join(error.message for error in self.errors)
        super().__init__(message)


def normalize_selection_plan(
    raw_plan: Mapping[str, Any],
    *,
    profile: CanonicalProfile,
    template_spec: TemplateSpec,
) -> SelectionPlan:
    errors: list[ValidationErrorDetail] = []

    document_type = _normalize_document_type(raw_plan.get("document_type", template_spec.document_type), errors)
    if document_type != template_spec.document_type:
        errors.append(
            ValidationErrorDetail(
                code="template_mismatch",
                message=(
                    f"Plan document_type {document_type!r} does not match template "
                    f"document_type {template_spec.document_type!r}."
                ),
                path="document_type",
                identifier=document_type,
            )
        )

    template_id = normalize_id(raw_plan.get("template_id", template_spec.id))
    if template_id != template_spec.id:
        errors.append(
            ValidationErrorDetail(
                code="template_mismatch",
                message=f"Plan template_id {template_id!r} does not match template {template_spec.id!r}.",
                path="template_id",
                identifier=template_id,
            )
        )

    sections = _normalize_id_list(
        raw_plan.get("sections", template_spec.section_order),
        path="sections",
        errors=errors,
    )
    _reject_unknown(
        sections,
        known_ids=set(template_spec.section_order),
        path="sections",
        code="unknown_section_id",
        label="section",
        errors=errors,
    )

    education_ids = _normalize_id_list(raw_plan.get("education_ids", []), path="education_ids", errors=errors)
    experience_ids = _normalize_id_list(raw_plan.get("experience_ids", []), path="experience_ids", errors=errors)
    project_ids = _normalize_id_list(raw_plan.get("project_ids", []), path="project_ids", errors=errors)

    education_by_id = profile.education_by_id()
    experiences_by_id = profile.experiences_by_id()
    projects_by_id = profile.projects_by_id()
    bullets_by_id = profile.bullets_by_id()
    bullets_by_owner_id = profile.bullets_by_owner_id()
    skills_by_group_id = profile.skills_by_group_id()

    _reject_unknown(
        education_ids,
        known_ids=set(education_by_id),
        path="education_ids",
        code="unknown_education_id",
        label="education",
        errors=errors,
    )
    _reject_unknown(
        experience_ids,
        known_ids=set(experiences_by_id),
        path="experience_ids",
        code="unknown_experience_id",
        label="experience",
        errors=errors,
    )
    _reject_unknown(
        project_ids,
        known_ids=set(projects_by_id),
        path="project_ids",
        code="unknown_project_id",
        label="project",
        errors=errors,
    )

    _reject_over_limit(education_ids, template_spec.max_education, "education_ids", "education", errors)
    _reject_over_limit(experience_ids, template_spec.max_experiences, "experience_ids", "experience", errors)
    _reject_over_limit(project_ids, template_spec.max_projects, "project_ids", "project", errors)

    bullet_ids_by_item = _normalize_id_mapping(
        raw_plan.get("bullet_ids_by_item", {}),
        path="bullet_ids_by_item",
        errors=errors,
    )
    selected_item_ids = {*experience_ids, *project_ids}
    valid_bullet_owner_ids = set(experiences_by_id) | set(projects_by_id)
    seen_bullet_ids: set[str] = set()
    for item_id, bullet_ids in bullet_ids_by_item:
        item_path = f"bullet_ids_by_item.{item_id}"
        if item_id not in valid_bullet_owner_ids:
            errors.append(
                ValidationErrorDetail(
                    code="unknown_bullet_owner_id",
                    message=f"Unknown bullet owner ID {item_id!r}.",
                    path=item_path,
                    identifier=item_id,
                )
            )
            continue
        if item_id not in selected_item_ids:
            errors.append(
                ValidationErrorDetail(
                    code="unselected_bullet_owner_id",
                    message=f"Bullet owner ID {item_id!r} is not selected by experience_ids or project_ids.",
                    path=item_path,
                    identifier=item_id,
                )
            )
        owner_bullets = bullets_by_owner_id.get(item_id, {})
        for bullet_id in bullet_ids:
            if bullet_id in seen_bullet_ids:
                errors.append(
                    ValidationErrorDetail(
                        code="duplicate_id",
                        message=f"Duplicate bullet ID {bullet_id!r}.",
                        path=item_path,
                        identifier=bullet_id,
                    )
                )
            seen_bullet_ids.add(bullet_id)
            bullet = bullets_by_id.get(bullet_id)
            if bullet is None:
                errors.append(
                    ValidationErrorDetail(
                        code="unknown_bullet_id",
                        message=f"Unknown bullet ID {bullet_id!r}.",
                        path=item_path,
                        identifier=bullet_id,
                    )
                )
                continue
            if bullet_id not in owner_bullets:
                errors.append(
                    ValidationErrorDetail(
                        code="wrong_bullet_owner",
                        message=f"Bullet ID {bullet_id!r} does not belong under item ID {item_id!r}.",
                        path=item_path,
                        identifier=bullet_id,
                    )
                )
        if item_id in experiences_by_id:
            _reject_over_limit(
                bullet_ids,
                template_spec.max_bullets_per_experience,
                item_path,
                "experience bullet",
                errors,
            )
        elif item_id in projects_by_id:
            _reject_over_limit(
                bullet_ids,
                template_spec.max_bullets_per_project,
                item_path,
                "project bullet",
                errors,
            )

    skill_ids_by_group = _normalize_id_mapping(
        raw_plan.get("skill_ids_by_group", {}),
        path="skill_ids_by_group",
        errors=errors,
    )
    allowed_skill_group_ids = {normalize_id(group_id) for group_id in template_spec.skill_group_order}
    seen_skill_ids: set[str] = set()
    for group_id, skill_ids in skill_ids_by_group:
        group_path = f"skill_ids_by_group.{group_id}"
        group_skills = skills_by_group_id.get(group_id)
        if group_skills is None:
            errors.append(
                ValidationErrorDetail(
                    code="unknown_skill_group_id",
                    message=f"Unknown skill group ID {group_id!r}.",
                    path=group_path,
                    identifier=group_id,
                )
            )
            continue
        if group_id not in allowed_skill_group_ids:
            errors.append(
                ValidationErrorDetail(
                    code="disallowed_skill_group_id",
                    message=f"Skill group ID {group_id!r} is not allowed by template {template_spec.id!r}.",
                    path=group_path,
                    identifier=group_id,
                )
            )
            continue
        _reject_over_limit(skill_ids, template_spec.max_skills_per_group, group_path, "skill", errors)
        for skill_id in skill_ids:
            if skill_id in seen_skill_ids:
                errors.append(
                    ValidationErrorDetail(
                        code="duplicate_id",
                        message=f"Duplicate skill ID {skill_id!r}.",
                        path=group_path,
                        identifier=skill_id,
                    )
                )
            seen_skill_ids.add(skill_id)
            skill = group_skills.get(skill_id)
            if skill is None:
                known_elsewhere = any(skill_id in group for group in skills_by_group_id.values())
                errors.append(
                    ValidationErrorDetail(
                        code="wrong_skill_group" if known_elsewhere else "unknown_skill_id",
                        message=f"Skill ID {skill_id!r} is not valid for skill group {group_id!r}.",
                        path=group_path,
                        identifier=skill_id,
                    )
                )

    if errors:
        raise PlanValidationError(errors)

    rationale = raw_plan.get("rationale")
    return SelectionPlan(
        document_type=document_type,  # type: ignore[arg-type]
        template_id=template_id,
        target=_normalize_target(raw_plan.get("target", {})),
        sections=sections,
        education_ids=education_ids,
        experience_ids=experience_ids,
        project_ids=project_ids,
        bullet_ids_by_item=bullet_ids_by_item,
        skill_ids_by_group=skill_ids_by_group,
        rationale=str(rationale) if rationale is not None else None,
    )


def selection_plan_artifact_json(plan: SelectionPlan) -> str:
    return json.dumps(plan.artifact_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_render_model(
    *,
    profile: CanonicalProfile,
    selection_plan: SelectionPlan,
    template_spec: TemplateSpec,
) -> RenderModel:
    if selection_plan.template_id != template_spec.id:
        raise ValueError(
            f"SelectionPlan template_id {selection_plan.template_id!r} does not match {template_spec.id!r}."
        )
    education_by_id = profile.education_by_id()
    experiences_by_id = profile.experiences_by_id()
    projects_by_id = profile.projects_by_id()
    bullets_by_owner_id = profile.bullets_by_owner_id()
    skills_by_group_id = profile.skills_by_group_id()

    bullet_ids_by_item = dict(selection_plan.bullet_ids_by_item)
    skill_ids_by_group = dict(selection_plan.skill_ids_by_group)

    selected_experiences = tuple(
        RenderExperience(
            entry=experiences_by_id[experience_id],
            bullets=tuple(
                bullets_by_owner_id[experience_id][bullet_id]
                for bullet_id in bullet_ids_by_item.get(experience_id, ())
            ),
        )
        for experience_id in selection_plan.experience_ids
    )
    selected_projects = tuple(
        RenderProject(
            entry=projects_by_id[project_id],
            bullets=tuple(
                bullets_by_owner_id[project_id][bullet_id] for bullet_id in bullet_ids_by_item.get(project_id, ())
            ),
        )
        for project_id in selection_plan.project_ids
    )
    selected_skill_groups = _select_skill_groups(profile, skill_ids_by_group, skills_by_group_id)

    return RenderModel(
        document_type=selection_plan.document_type,
        template_id=selection_plan.template_id,
        contact=profile.contact,
        target=selection_plan.target,
        sections=selection_plan.sections,
        education=tuple(education_by_id[education_id] for education_id in selection_plan.education_ids),
        experiences=selected_experiences,
        projects=selected_projects,
        skills=selected_skill_groups,
    )


def _select_skill_groups(
    profile: CanonicalProfile,
    skill_ids_by_group: dict[str, tuple[str, ...]],
    skills_by_group_id: dict[str, dict[str, SkillItem]],
) -> tuple[SkillGroup, ...]:
    groups: list[SkillGroup] = []
    for group in profile.skill_groups:
        selected_skill_ids = skill_ids_by_group.get(group.id)
        if selected_skill_ids is None:
            continue
        groups.append(
            SkillGroup(
                id=group.id,
                label=group.label,
                skills=tuple(skills_by_group_id[group.id][skill_id] for skill_id in selected_skill_ids),
            )
        )
    return tuple(groups)


def _normalize_document_type(value: Any, errors: list[ValidationErrorDetail]) -> str:
    document_type = normalize_id(value).replace("-", "_")
    if document_type not in {"resume", "cover_letter"}:
        errors.append(
            ValidationErrorDetail(
                code="invalid_document_type",
                message=f"Invalid document_type {document_type!r}.",
                path="document_type",
                identifier=document_type,
            )
        )
    return document_type


def _normalize_target(raw_target: Any) -> Target:
    if not isinstance(raw_target, Mapping):
        raw_target = {}
    return Target(
        company=str(raw_target.get("company", "") or "").strip(),
        role=str(raw_target.get("role", "") or "").strip(),
    )


def _normalize_id_list(raw_value: Any, *, path: str, errors: list[ValidationErrorDetail]) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    if not isinstance(raw_value, list | tuple):
        errors.append(
            ValidationErrorDetail(
                code="invalid_type",
                message=f"{path} must be a list of IDs.",
                path=path,
            )
        )
        return ()
    ids: list[str] = []
    seen: set[str] = set()
    for index, raw_id in enumerate(raw_value):
        normalized_id = normalize_id(raw_id)
        item_path = f"{path}[{index}]"
        if not normalized_id:
            errors.append(
                ValidationErrorDetail(
                    code="invalid_id",
                    message=f"{item_path} must not be empty.",
                    path=item_path,
                )
            )
            continue
        if normalized_id in seen:
            errors.append(
                ValidationErrorDetail(
                    code="duplicate_id",
                    message=f"Duplicate ID {normalized_id!r} in {path}.",
                    path=item_path,
                    identifier=normalized_id,
                )
            )
        seen.add(normalized_id)
        ids.append(normalized_id)
    return tuple(ids)


def _normalize_id_mapping(raw_value: Any, *, path: str, errors: list[ValidationErrorDetail]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if raw_value is None:
        return ()
    if not isinstance(raw_value, Mapping):
        errors.append(
            ValidationErrorDetail(
                code="invalid_type",
                message=f"{path} must be an object mapping IDs to ID lists.",
                path=path,
            )
        )
        return ()
    normalized_items: list[tuple[str, tuple[str, ...]]] = []
    seen_keys: set[str] = set()
    for raw_key, raw_ids in raw_value.items():
        key = normalize_id(raw_key)
        key_path = f"{path}.{key}"
        if not key:
            errors.append(
                ValidationErrorDetail(
                    code="invalid_id",
                    message=f"{path} keys must not be empty.",
                    path=path,
                )
            )
            continue
        if key in seen_keys:
            errors.append(
                ValidationErrorDetail(
                    code="duplicate_id",
                    message=f"Duplicate mapping key {key!r} in {path}.",
                    path=key_path,
                    identifier=key,
                )
            )
        seen_keys.add(key)
        normalized_items.append((key, _normalize_id_list(raw_ids, path=key_path, errors=errors)))
    return tuple(normalized_items)


def _reject_unknown(
    ids: tuple[str, ...],
    *,
    known_ids: set[str],
    path: str,
    code: str,
    label: str,
    errors: list[ValidationErrorDetail],
) -> None:
    for identifier in ids:
        if identifier not in known_ids:
            errors.append(
                ValidationErrorDetail(
                    code=code,
                    message=f"Unknown {label} ID {identifier!r}.",
                    path=path,
                    identifier=identifier,
                )
            )


def _reject_over_limit(
    ids: tuple[str, ...],
    maximum: int | None,
    path: str,
    label: str,
    errors: list[ValidationErrorDetail],
) -> None:
    if maximum is None or len(ids) <= maximum:
        return
    errors.append(
        ValidationErrorDetail(
            code="limit_exceeded",
            message=f"{path} selects {len(ids)} {label} IDs; template maximum is {maximum}.",
            path=path,
        )
    )
