"""Ports for raw job ingestion and ETL posting compilation."""

from __future__ import annotations

from typing import Protocol

from ..core.domain.ingestion import JobPosting, RawJobPayload


class RawFetcherPort(Protocol):
    """Outbound port for fetching raw posting content from the web."""

    def fetch(self, url: str, timeout: float = 10.0) -> RawJobPayload: ...


class JobTransformerPort(Protocol):
    """Port for compiling raw payloads into normalized JobPosting domain entities."""

    def transform(
        self,
        raw: RawJobPayload,
        company_override: str = "",
        role_override: str = "",
    ) -> JobPosting: ...
