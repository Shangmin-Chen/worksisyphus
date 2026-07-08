from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .artifacts import atomic_write_text, canonical_json, canonical_profile_hash, sha256_text
from .models import CanonicalProfile, SelectionPlan, TemplateSpec, ValidationErrorDetail
from .selection import PlanValidationError, normalize_selection_plan, selection_plan_artifact_json


PLANNER_PROMPT_VERSION = "selection-planner-prompt-v1"
PLANNER_SCHEMA_VERSION = "selection-plan-v1"
PLAN_CACHE_KEY_VERSION = "plan-cache-key-v2"
DEFAULT_PLANNER_MODEL_ID = "gemini-planner"

_FENCED_JSON_RE = re.compile(r"```\s*(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
_DOCUMENT_COMMAND_RE = re.compile(
    r"\\(?:documentclass|usepackage|begin\s*\{\s*document\s*\}|end\s*\{\s*document\s*\}|"
    r"newcommand|section\s*\{|resume(?:Item|Subheading|ProjectHeading))"
)


class PlannerJsonError(ValueError):
    pass


PlannerModel = Callable[[str], Any]


@dataclass(frozen=True)
class PlannerResult:
    plan: SelectionPlan
    cache_key: str
    from_cache: bool
    used_fallback: bool
    raw_planner_text: str
    raw_planner_json: Mapping[str, Any] | None
    validation_status: str
    validation_report: Mapping[str, Any]


def raw_input_hash(raw_input: str) -> str:
    return sha256_text(raw_input)


def plan_cache_key(
    *,
    raw_input_hash_value: str,
    canonical_profile_hash_value: str,
    template_id: str,
    prompt_version: str,
    model_id: str,
    planner_schema_version: str,
    template_spec_hash_value: str | None = None,
) -> str:
    payload = {
        "cache_key_version": PLAN_CACHE_KEY_VERSION,
        "canonical_profile_hash": canonical_profile_hash_value,
        "model_id": model_id,
        "planner_schema_version": planner_schema_version,
        "prompt_version": prompt_version,
        "raw_input_hash": raw_input_hash_value,
        "template_id": template_id,
    }
    if template_spec_hash_value is not None:
        payload["template_spec_hash"] = template_spec_hash_value
    return sha256_text(canonical_json(payload))


def planner_template_spec_hash(template_spec: TemplateSpec) -> str:
    return sha256_text(canonical_json(_planner_template_spec_dict(template_spec)))


def build_planner_prompt(
    *,
    raw_input: str,
    profile: CanonicalProfile,
    template_spec: TemplateSpec,
    prompt_version: str = PLANNER_PROMPT_VERSION,
    planner_schema_version: str = PLANNER_SCHEMA_VERSION,
) -> str:
    prompt_payload = {
        "canonical_index": _canonical_index(profile),
        "output_contract": {
            "format": "json_object_only",
            "planner_schema_version": planner_schema_version,
            "selection_plan_shape": {
                "document_type": template_spec.document_type,
                "template_id": template_spec.id,
                "target": {"company": "string", "role": "string"},
                "sections": list(template_spec.section_order),
                "education_ids": ["education:id"],
                "experience_ids": ["experience:id"],
                "project_ids": ["project:id"],
                "bullet_ids_by_item": {"experience-or-project:id": ["bullet:id"]},
                "skill_ids_by_group": {"skill_group_id": ["skill:id"]},
                "rationale": "optional string",
            },
        },
        "prompt_version": prompt_version,
        "raw_input": raw_input,
        "rules": [
            "Return one JSON object only.",
            "Include every field shown in selection_plan_shape, using empty lists or objects when nothing is selected.",
            "Use only IDs listed in canonical_index.",
            "Respect every max count in template_spec.",
            "Preserve the requested section order from template_spec unless the raw input clearly asks otherwise.",
            "Leave target fields empty when the company or role is not stated.",
            "Do not include markdown, commentary, or code fences.",
        ],
        "template_spec": _planner_template_spec_dict(template_spec),
    }
    return (
        "You select canonical IDs for a structured resume or cover-letter plan.\n"
        "Respond with the requested JSON object and nothing else.\n"
        + json.dumps(prompt_payload, indent=2, sort_keys=True, ensure_ascii=False)
    )


def parse_planner_json(text: str) -> dict[str, Any]:
    if _DOCUMENT_COMMAND_RE.search(text):
        raise PlannerJsonError("Planner output contained non-JSON document commands.")

    stripped = text.strip()
    if not stripped:
        raise PlannerJsonError("Planner output was empty.")

    candidates = [match.group(1).strip() for match in _FENCED_JSON_RE.finditer(stripped)]
    candidates.append(stripped)
    last_error: Exception | None = None
    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if not isinstance(parsed, dict):
            raise PlannerJsonError("Planner output JSON must be an object.")
        return parsed

    if last_error is not None:
        raise PlannerJsonError(f"Planner output was not valid JSON: {last_error.msg}.") from last_error
    raise PlannerJsonError("Planner output did not contain JSON.")


def validate_planner_plan_shape(
    raw_plan: Mapping[str, Any],
    *,
    profile: CanonicalProfile,
    template_spec: TemplateSpec,
) -> None:
    errors: list[ValidationErrorDetail] = []
    required_fields = (
        "document_type",
        "template_id",
        "target",
        "sections",
        "education_ids",
        "experience_ids",
        "project_ids",
        "bullet_ids_by_item",
        "skill_ids_by_group",
    )
    for field in required_fields:
        if field not in raw_plan:
            errors.append(
                ValidationErrorDetail(
                    code="missing_required_field",
                    message=f"Planner output must include {field!r}.",
                    path=field,
                )
            )

    target = raw_plan.get("target")
    if "target" in raw_plan and not isinstance(target, Mapping):
        errors.append(
            ValidationErrorDetail(
                code="invalid_required_field",
                message="Planner output target must be an object.",
                path="target",
            )
        )

    sections = raw_plan.get("sections")
    if "sections" in raw_plan and not isinstance(sections, list | tuple):
        errors.append(
            ValidationErrorDetail(
                code="invalid_required_field",
                message="Planner output sections must be a list.",
                path="sections",
            )
        )

    for field in ("education_ids", "experience_ids", "project_ids"):
        value = raw_plan.get(field)
        if field in raw_plan and not isinstance(value, list | tuple):
            errors.append(
                ValidationErrorDetail(
                    code="invalid_required_field",
                    message=f"Planner output {field} must be a list.",
                    path=field,
                )
            )

    for field in ("bullet_ids_by_item", "skill_ids_by_group"):
        value = raw_plan.get(field)
        if field in raw_plan and not isinstance(value, Mapping):
            errors.append(
                ValidationErrorDetail(
                    code="invalid_required_field",
                    message=f"Planner output {field} must be an object.",
                    path=field,
                )
            )

    if not _has_selectable_content(raw_plan, template_spec=template_spec) and _profile_has_selectable_content(
        profile,
        template_spec=template_spec,
    ):
        errors.append(
            ValidationErrorDetail(
                code="missing_selectable_content",
                message="Planner output must select at least one canonical education, experience, project, or skill ID.",
                path="",
            )
        )

    if errors:
        raise PlanValidationError(errors)


def deterministic_fallback_selection_plan(
    *,
    profile: CanonicalProfile,
    template_spec: TemplateSpec,
) -> SelectionPlan:
    max_education = _limit(template_spec.max_education, len(profile.education))
    max_experiences = _limit(template_spec.max_experiences, len(profile.experiences))
    max_projects = _limit(template_spec.max_projects, len(profile.projects))
    selected_education = profile.education[:max_education]
    selected_experiences = profile.experiences[:max_experiences]
    selected_projects = profile.projects[:max_projects]

    bullet_ids_by_item: dict[str, list[str]] = {}
    for experience in selected_experiences:
        max_bullets = _limit(template_spec.max_bullets_per_experience, len(experience.bullets))
        bullet_ids_by_item[experience.id] = [bullet.id for bullet in experience.bullets[:max_bullets]]
    for project in selected_projects:
        max_bullets = _limit(template_spec.max_bullets_per_project, len(project.bullets))
        bullet_ids_by_item[project.id] = [bullet.id for bullet in project.bullets[:max_bullets]]

    groups_by_id = profile.skill_groups_by_id()
    skill_ids_by_group: dict[str, list[str]] = {}
    for group_id in template_spec.skill_group_order:
        group = groups_by_id.get(group_id)
        if group is None:
            continue
        max_skills = _limit(template_spec.max_skills_per_group, len(group.skills))
        skill_ids_by_group[group.id] = [skill.id for skill in group.skills[:max_skills]]

    raw_plan = {
        "document_type": template_spec.document_type,
        "template_id": template_spec.id,
        "target": {"company": "", "role": ""},
        "sections": list(template_spec.section_order),
        "education_ids": [entry.id for entry in selected_education],
        "experience_ids": [entry.id for entry in selected_experiences],
        "project_ids": [entry.id for entry in selected_projects],
        "bullet_ids_by_item": bullet_ids_by_item,
        "skill_ids_by_group": skill_ids_by_group,
        "rationale": "Deterministic baseline selection.",
    }
    return normalize_selection_plan(raw_plan, profile=profile, template_spec=template_spec)


class PlanCache:
    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)

    def record_path(self, key: str) -> Path:
        return self.cache_dir / "plans" / f"{key}.json"

    def read_record(self, key: str) -> dict[str, Any] | None:
        path = self.record_path(key)
        if not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as cache_file:
            value = json.load(cache_file)
        return value if isinstance(value, dict) else None

    def read_normalized_plan(
        self,
        *,
        key: str,
        profile: CanonicalProfile,
        template_spec: TemplateSpec,
    ) -> tuple[SelectionPlan, dict[str, Any]] | None:
        record = self.read_record(key)
        if record is None:
            return None
        if record.get("validation_status") not in {"valid", "fallback_valid"}:
            return None
        normalized_json = record.get("normalized_plan_json", record.get("normalized_artifact_json"))
        if not isinstance(normalized_json, str):
            return None
        try:
            raw_plan = json.loads(normalized_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(raw_plan, dict):
            return None
        if record.get("validation_status") == "valid":
            try:
                validate_planner_plan_shape(raw_plan, profile=profile, template_spec=template_spec)
            except PlanValidationError:
                return None
        try:
            plan = normalize_selection_plan(raw_plan, profile=profile, template_spec=template_spec)
        except PlanValidationError:
            return None
        return plan, record

    def write_record(self, *, key: str, record: Mapping[str, Any]) -> Path:
        return atomic_write_text(self.record_path(key), canonical_json(dict(record)) + "\n")


class GeminiPlanner:
    def __init__(
        self,
        model: PlannerModel | Any | None,
        *,
        cache: PlanCache | None = None,
        model_id: str = DEFAULT_PLANNER_MODEL_ID,
        prompt_version: str = PLANNER_PROMPT_VERSION,
        planner_schema_version: str = PLANNER_SCHEMA_VERSION,
    ) -> None:
        self.model = model
        self.cache = cache
        self.model_id = model_id
        self.prompt_version = prompt_version
        self.planner_schema_version = planner_schema_version

    def plan(
        self,
        *,
        raw_input: str,
        profile: CanonicalProfile,
        template_spec: TemplateSpec,
        metadata: Mapping[str, Any] | None = None,
    ) -> PlannerResult:
        profile_hash = canonical_profile_hash(profile)
        input_hash = raw_input_hash(raw_input)
        key = plan_cache_key(
            raw_input_hash_value=input_hash,
            canonical_profile_hash_value=profile_hash,
            template_id=template_spec.id,
            prompt_version=self.prompt_version,
            model_id=self.model_id,
            planner_schema_version=self.planner_schema_version,
            template_spec_hash_value=planner_template_spec_hash(template_spec),
        )

        if self.cache is not None:
            cached = self.cache.read_normalized_plan(key=key, profile=profile, template_spec=template_spec)
            if cached is not None:
                plan, record = cached
                raw_json = record.get("raw_planner_json")
                return PlannerResult(
                    plan=plan,
                    cache_key=key,
                    from_cache=True,
                    used_fallback=record.get("validation_status") == "fallback_valid",
                    raw_planner_text=str(record.get("raw_planner_text", "")),
                    raw_planner_json=raw_json if isinstance(raw_json, Mapping) else None,
                    validation_status=str(record.get("validation_status", "")),
                    validation_report=_record_validation_report(record),
                )

        prompt = build_planner_prompt(
            raw_input=raw_input,
            profile=profile,
            template_spec=template_spec,
            prompt_version=self.prompt_version,
            planner_schema_version=self.planner_schema_version,
        )

        raw_text = ""
        raw_json: dict[str, Any] | None = None
        try:
            raw_text = _call_model(self.model, prompt)
            raw_json = parse_planner_json(raw_text)
            validate_planner_plan_shape(raw_json, profile=profile, template_spec=template_spec)
            plan = normalize_selection_plan(raw_json, profile=profile, template_spec=template_spec)
            validation_report = {"model": {"status": "valid", "errors": []}}
            record = self._cache_record(
                key=key,
                raw_input_hash_value=input_hash,
                canonical_profile_hash_value=profile_hash,
                template_spec=template_spec,
                raw_planner_text=raw_text,
                raw_planner_json=raw_json,
                normalized_plan=plan,
                validation_status="valid",
                validation_report=validation_report,
                metadata=metadata,
            )
            self._write_record(key, record)
            return PlannerResult(
                plan=plan,
                cache_key=key,
                from_cache=False,
                used_fallback=False,
                raw_planner_text=raw_text,
                raw_planner_json=raw_json,
                validation_status="valid",
                validation_report=validation_report,
            )
        except Exception as exc:
            fallback_plan = deterministic_fallback_selection_plan(profile=profile, template_spec=template_spec)
            validation_report = {
                "fallback": {"status": "valid", "errors": []},
                "model": _failure_report(exc),
            }
            record = self._cache_record(
                key=key,
                raw_input_hash_value=input_hash,
                canonical_profile_hash_value=profile_hash,
                template_spec=template_spec,
                raw_planner_text=raw_text,
                raw_planner_json=raw_json,
                normalized_plan=fallback_plan,
                validation_status="fallback_valid",
                validation_report=validation_report,
                metadata=metadata,
            )
            self._write_record(key, record)
            return PlannerResult(
                plan=fallback_plan,
                cache_key=key,
                from_cache=False,
                used_fallback=True,
                raw_planner_text=raw_text,
                raw_planner_json=raw_json,
                validation_status="fallback_valid",
                validation_report=validation_report,
            )

    def _cache_record(
        self,
        *,
        key: str,
        raw_input_hash_value: str,
        canonical_profile_hash_value: str,
        template_spec: TemplateSpec,
        raw_planner_text: str,
        raw_planner_json: Mapping[str, Any] | None,
        normalized_plan: SelectionPlan,
        validation_status: str,
        validation_report: Mapping[str, Any],
        metadata: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "cache_key": key,
            "cache_key_version": PLAN_CACHE_KEY_VERSION,
            "canonical_profile_hash": canonical_profile_hash_value,
            "created_at": _utc_timestamp(),
            "metadata": dict(metadata or {}),
            "model_id": self.model_id,
            "normalized_artifact_json": selection_plan_artifact_json(normalized_plan),
            "normalized_plan_json": _selection_plan_full_json(normalized_plan),
            "planner_schema_version": self.planner_schema_version,
            "prompt_version": self.prompt_version,
            "raw_input_hash": raw_input_hash_value,
            "raw_planner_json": dict(raw_planner_json) if raw_planner_json is not None else None,
            "raw_planner_text": raw_planner_text,
            "template_id": template_spec.id,
            "template_spec_hash": planner_template_spec_hash(template_spec),
            "template_version": template_spec.version,
            "validation_report": dict(validation_report),
            "validation_status": validation_status,
        }

    def _write_record(self, key: str, record: Mapping[str, Any]) -> None:
        if self.cache is not None:
            self.cache.write_record(key=key, record=record)


def _call_model(model: PlannerModel | Any | None, prompt: str) -> str:
    if model is None:
        raise RuntimeError("No planner model is configured.")
    if callable(model):
        response = model(prompt)
    elif hasattr(model, "generate_content"):
        response = model.generate_content(prompt)
    else:
        raise TypeError("Planner model must be callable or expose generate_content.")
    return _response_text(response)


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, bytes):
        return response.decode("utf-8")
    if isinstance(response, Mapping):
        return canonical_json(response)
    text = getattr(response, "text", None)
    if text is not None:
        return str(text)
    content = getattr(response, "content", None)
    if content is not None:
        return str(content)
    raise TypeError("Planner model response did not contain text.")


def _failure_report(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, PlannerJsonError):
        return {
            "status": "invalid_json",
            "errors": [{"code": "invalid_json", "message": str(exc), "path": ""}],
        }
    if isinstance(exc, PlanValidationError):
        return {
            "status": "invalid_plan",
            "errors": [dataclasses.asdict(error) for error in exc.errors],
        }
    return {
        "status": "model_error",
        "errors": [{"code": exc.__class__.__name__, "message": str(exc), "path": ""}],
    }


def _record_validation_report(record: Mapping[str, Any]) -> Mapping[str, Any]:
    report = record.get("validation_report")
    return report if isinstance(report, Mapping) else {}


def _selection_plan_full_json(plan: SelectionPlan) -> str:
    return canonical_json(
        {
            **plan.artifact_dict(),
            "rationale": plan.rationale,
        }
    )


def _has_selectable_content(raw_plan: Mapping[str, Any], *, template_spec: TemplateSpec) -> bool:
    if template_spec.max_education != 0 and _has_items(raw_plan.get("education_ids")):
        return True
    if template_spec.max_experiences != 0 and _has_items(raw_plan.get("experience_ids")):
        return True
    if template_spec.max_projects != 0 and _has_items(raw_plan.get("project_ids")):
        return True
    if template_spec.max_skills_per_group != 0 and _mapping_has_items(raw_plan.get("skill_ids_by_group")):
        return True
    return False


def _has_items(value: Any) -> bool:
    return isinstance(value, list | tuple) and any(str(item).strip() for item in value)


def _mapping_has_items(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return any(_has_items(items) for items in value.values())


def _profile_has_selectable_content(profile: CanonicalProfile, *, template_spec: TemplateSpec) -> bool:
    if template_spec.max_education != 0 and profile.education:
        return True
    if template_spec.max_experiences != 0 and profile.experiences:
        return True
    if template_spec.max_projects != 0 and profile.projects:
        return True
    if template_spec.max_skills_per_group != 0:
        allowed_group_ids = set(template_spec.skill_group_order)
        for group in profile.skill_groups:
            if group.id in allowed_group_ids and group.skills:
                return True
    return False


def _planner_template_spec_dict(template_spec: TemplateSpec) -> dict[str, Any]:
    return {
        "document_type": template_spec.document_type,
        "id": template_spec.id,
        "max_bullets_per_experience": template_spec.max_bullets_per_experience,
        "max_bullets_per_project": template_spec.max_bullets_per_project,
        "max_education": template_spec.max_education,
        "max_experiences": template_spec.max_experiences,
        "max_projects": template_spec.max_projects,
        "max_skills_per_group": template_spec.max_skills_per_group,
        "page_limit": template_spec.page_limit,
        "section_order": list(template_spec.section_order),
        "skill_group_order": list(template_spec.skill_group_order),
        "version": template_spec.version,
    }


def _canonical_index(profile: CanonicalProfile) -> dict[str, Any]:
    return {
        "education": [
            {
                "date": entry.date,
                "degree": entry.degree,
                "id": entry.id,
                "institution": entry.institution,
            }
            for entry in profile.education
        ],
        "experiences": [
            {
                "bullet_ids": [{"id": bullet.id, "text": bullet.text} for bullet in entry.bullets],
                "date": entry.date,
                "id": entry.id,
                "organization": entry.organization,
                "role": entry.role,
            }
            for entry in profile.experiences
        ],
        "projects": [
            {
                "bullet_ids": [{"id": bullet.id, "text": bullet.text} for bullet in entry.bullets],
                "date": entry.date,
                "id": entry.id,
                "name": entry.name,
                "technologies": entry.technologies,
            }
            for entry in profile.projects
        ],
        "skill_groups": [
            {
                "id": group.id,
                "label": group.label,
                "skill_ids": [{"id": skill.id, "label": skill.label} for skill in group.skills],
            }
            for group in profile.skill_groups
        ],
    }


def _limit(maximum: int | None, available: int) -> int:
    return available if maximum is None else min(maximum, available)


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
