"""Backward-compatibility facade for application use cases."""

from __future__ import annotations

import os
import sys

from .core.use_cases import application as _module
from .core.use_cases.application import (
    _MAX_FOLDER_NAME_BYTES,
    _ORDINAL_SUFFIX_MARGIN,
    APPLICATIONS_DIR,
    STATUSES,
    TEX_BUILD_PREFIX,
    _allocate_target,
    application_sort_key,
    apply,
    backfill_evaluations,
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

sys.modules[__name__] = _module

__all__ = [
    "APPLICATIONS_DIR",
    "STATUSES",
    "TEX_BUILD_PREFIX",
    "_MAX_FOLDER_NAME_BYTES",
    "_ORDINAL_SUFFIX_MARGIN",
    "_allocate_target",
    "application_sort_key",
    "apply",
    "backfill_evaluations",
    "cross_check_contact_against_db",
    "evaluate_application",
    "list_applications",
    "match_application_identifier",
    "os",
    "parse_app_folder",
    "resolve_application_folder",
    "slugify",
    "sorted_application_names",
    "update_application_status",
]
