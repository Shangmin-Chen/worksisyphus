"""Backward-compatibility facade for profile data and loader."""

from __future__ import annotations

from .adapters.outbound.filesystem.profile_loader import load_profile
from .core.domain.models import (
    DEFAULT_PROFILE_PATH,
    REQUIRED_CONTACT_FIELDS,
    Contact,
    Education,
    Experience,
    Profile,
    Project,
    profile_index,
    profile_to_dict,
    validate_contact,
)

__all__ = [
    "DEFAULT_PROFILE_PATH",
    "REQUIRED_CONTACT_FIELDS",
    "Contact",
    "Education",
    "Experience",
    "Profile",
    "Project",
    "load_profile",
    "profile_index",
    "profile_to_dict",
    "validate_contact",
]
