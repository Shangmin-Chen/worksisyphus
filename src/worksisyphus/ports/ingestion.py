"""Ports for raw job ingestion and web fetching."""

from __future__ import annotations

from typing import Protocol

from ..core.domain.ingestion import RawJobPayload


class RawFetcherPort(Protocol):
    """Outbound port for fetching raw posting content from the web."""

    def fetch(self, url: str, timeout: float = 10.0) -> RawJobPayload: ...
