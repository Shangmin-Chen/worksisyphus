"""Outbound adapters for raw job ingestion, HTML cleaning, scratch management, and ETL."""

from .etl_compiler import EtlJobTransformer
from .http_fetcher import HttpRawFetcher, resolve_ats_endpoint
from .pre_cleaner import PreCleaner, clean_html
from .scratch_bridge import DEFAULT_SCRATCH_DIR, ScratchBridge

__all__ = [
    "DEFAULT_SCRATCH_DIR",
    "EtlJobTransformer",
    "HttpRawFetcher",
    "PreCleaner",
    "ScratchBridge",
    "clean_html",
    "resolve_ats_endpoint",
]
