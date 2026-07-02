"""Persistent job catalog state."""

from worksisyphus.catalog.db import (
    application_status,
    enrichment_exists,
    init_catalog,
    mark_applied,
    upsert_enrichment,
    upsert_normalized_jobs,
)

__all__ = [
    "application_status",
    "enrichment_exists",
    "init_catalog",
    "mark_applied",
    "upsert_enrichment",
    "upsert_normalized_jobs",
]
