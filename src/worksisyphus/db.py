"""Backward-compatibility facade for SQLite persistence."""

from __future__ import annotations

import sys

from .adapters.outbound.persistence import sqlite as _module
from .adapters.outbound.persistence.sqlite import (
    ACTION_APPLY,
    ACTION_DELETE,
    ACTION_INSERT,
    ACTION_STATUS_CHANGE,
    ACTION_UPDATE,
    DEFAULT_DB_PATH,
    SqliteStorageAdapter,
    SqliteTursoAdapter,
    export_profile_json,
    get_audit_history,
    get_connection,
    init_schema,
    list_applications_from_db,
    load_profile_from_db,
    log_audit_event,
    save_application_to_db,
    seed_database,
    update_application_status_in_db,
)

sys.modules[__name__] = _module

__all__ = [
    "ACTION_APPLY",
    "ACTION_DELETE",
    "ACTION_INSERT",
    "ACTION_STATUS_CHANGE",
    "ACTION_UPDATE",
    "DEFAULT_DB_PATH",
    "SqliteStorageAdapter",
    "SqliteTursoAdapter",
    "export_profile_json",
    "get_audit_history",
    "get_connection",
    "init_schema",
    "list_applications_from_db",
    "load_profile_from_db",
    "log_audit_event",
    "save_application_to_db",
    "seed_database",
    "update_application_status_in_db",
]
