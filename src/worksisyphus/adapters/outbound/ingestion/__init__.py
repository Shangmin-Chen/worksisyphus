"""Outbound adapters for raw web ingestion, HTML noise removal, and scratch management."""

from .http_fetcher import HttpRawFetcher
from .pre_cleaner import PreCleaner, clean_html
from .scratch_bridge import DEFAULT_SCRATCH_DIR, ScratchBridge

__all__ = [
    "DEFAULT_SCRATCH_DIR",
    "HttpRawFetcher",
    "PreCleaner",
    "ScratchBridge",
    "clean_html",
]
