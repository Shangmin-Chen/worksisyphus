"""Backwards-compatible wrapper module for application lifecycle functions."""

from __future__ import annotations

from .application import (
    APPLICATIONS_DIR,
    STATUSES,
    apply,
    archive_application,
    list_applications,
    resolve_application_folder,
    slugify,
    update_application_status,
)

__all__ = [
    "APPLICATIONS_DIR",
    "STATUSES",
    "apply",
    "archive_application",
    "list_applications",
    "resolve_application_folder",
    "slugify",
    "update_application_status",
]
