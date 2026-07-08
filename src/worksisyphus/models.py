from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


DocumentType = Literal["resume", "cover_letter"]


@dataclass(frozen=True)
class ValidationErrorDetail:
    code: str
    message: str
    path: str
    identifier: str | None = None


@dataclass(frozen=True)
class TemplateSpec:
    id: str
    version: str
    document_type: DocumentType
    source_template: str
    section_order: tuple[str, ...]
    max_education: int | None = None
    max_experiences: int | None = None
    max_projects: int | None = None
    max_bullets_per_experience: int | None = None
    max_bullets_per_project: int | None = None
    max_skills_per_group: int | None = None
    skill_group_order: tuple[str, ...] = ()
    page_limit: int | None = None
    preamble: str = ""
    command_profile: str = ""
    spacing_profile: str = ""


@dataclass(frozen=True)
class Contact:
    name: str = ""
    email: str = ""
    phone: str = ""
    website: str = ""
    github: str = ""
    linkedin: str = ""


@dataclass(frozen=True)
class Bullet:
    id: str
    text: str
    owner_id: str
    owner_type: Literal["experience", "project"]
    source_index: int


@dataclass(frozen=True)
class EducationEntry:
    id: str
    institution: str
    location: str
    degree: str
    date: str
    coursework: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExperienceEntry:
    id: str
    organization: str
    location: str
    role: str
    date: str
    bullets: tuple[Bullet, ...] = ()


@dataclass(frozen=True)
class ProjectEntry:
    id: str
    name: str
    technologies: str
    date: str
    bullets: tuple[Bullet, ...] = ()


@dataclass(frozen=True)
class SkillItem:
    id: str
    label: str
    group_id: str


@dataclass(frozen=True)
class SkillGroup:
    id: str
    label: str
    skills: tuple[SkillItem, ...] = ()


@dataclass(frozen=True)
class CanonicalProfile:
    contact: Contact
    education: tuple[EducationEntry, ...] = ()
    experiences: tuple[ExperienceEntry, ...] = ()
    projects: tuple[ProjectEntry, ...] = ()
    skill_groups: tuple[SkillGroup, ...] = ()

    def education_by_id(self) -> dict[str, EducationEntry]:
        return {entry.id: entry for entry in self.education}

    def experiences_by_id(self) -> dict[str, ExperienceEntry]:
        return {entry.id: entry for entry in self.experiences}

    def projects_by_id(self) -> dict[str, ProjectEntry]:
        return {entry.id: entry for entry in self.projects}

    def skill_groups_by_id(self) -> dict[str, SkillGroup]:
        return {group.id: group for group in self.skill_groups}

    def bullets_by_id(self) -> dict[str, Bullet]:
        bullets: dict[str, Bullet] = {}
        for item in (*self.experiences, *self.projects):
            for bullet in item.bullets:
                bullets[bullet.id] = bullet
        return bullets

    def bullets_by_owner_id(self) -> dict[str, dict[str, Bullet]]:
        bullets_by_owner: dict[str, dict[str, Bullet]] = {}
        for item in (*self.experiences, *self.projects):
            bullets_by_owner[item.id] = {bullet.id: bullet for bullet in item.bullets}
        return bullets_by_owner

    def skills_by_group_id(self) -> dict[str, dict[str, SkillItem]]:
        return {group.id: {skill.id: skill for skill in group.skills} for group in self.skill_groups}


@dataclass(frozen=True)
class Target:
    company: str = ""
    role: str = ""


@dataclass(frozen=True)
class SelectionPlan:
    document_type: DocumentType
    template_id: str
    target: Target
    sections: tuple[str, ...]
    education_ids: tuple[str, ...] = ()
    experience_ids: tuple[str, ...] = ()
    project_ids: tuple[str, ...] = ()
    bullet_ids_by_item: tuple[tuple[str, tuple[str, ...]], ...] = ()
    skill_ids_by_group: tuple[tuple[str, tuple[str, ...]], ...] = ()
    rationale: str | None = None

    def artifact_dict(self) -> dict[str, Any]:
        return {
            "bullet_ids_by_item": {item_id: list(bullet_ids) for item_id, bullet_ids in self.bullet_ids_by_item},
            "document_type": self.document_type,
            "education_ids": list(self.education_ids),
            "experience_ids": list(self.experience_ids),
            "project_ids": list(self.project_ids),
            "sections": list(self.sections),
            "skill_ids_by_group": {
                group_id: list(skill_ids) for group_id, skill_ids in self.skill_ids_by_group
            },
            "target": {
                "company": self.target.company,
                "role": self.target.role,
            },
            "template_id": self.template_id,
        }


@dataclass(frozen=True)
class RenderExperience:
    entry: ExperienceEntry
    bullets: tuple[Bullet, ...]


@dataclass(frozen=True)
class RenderProject:
    entry: ProjectEntry
    bullets: tuple[Bullet, ...]


@dataclass(frozen=True)
class RenderModel:
    document_type: DocumentType
    template_id: str
    contact: Contact
    target: Target
    sections: tuple[str, ...]
    education: tuple[EducationEntry, ...]
    experiences: tuple[RenderExperience, ...]
    projects: tuple[RenderProject, ...]
    skills: tuple[SkillGroup, ...]
