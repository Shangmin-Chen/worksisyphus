"""Unit tests for HttpRawFetcher and ATS endpoint resolution."""

from __future__ import annotations

import io
import urllib.error
from typing import Any

import pytest

from worksisyphus.adapters.outbound.ingestion.http_fetcher import (
    HttpRawFetcher,
    resolve_ats_endpoint,
)


def test_resolve_ats_endpoint_greenhouse() -> None:
    url = "https://boards.greenhouse.io/stripe/jobs/5123456"
    api_url, hint = resolve_ats_endpoint(url)
    assert api_url == "https://boards-api.greenhouse.io/v1/boards/stripe/jobs/5123456?questions=true"
    assert hint == "greenhouse"

    url_job_boards = "https://job-boards.greenhouse.io/stripe/jobs/5123456"
    api_url2, hint2 = resolve_ats_endpoint(url_job_boards)
    assert api_url2 == "https://boards-api.greenhouse.io/v1/boards/stripe/jobs/5123456?questions=true"
    assert hint2 == "greenhouse"


def test_resolve_ats_endpoint_lever() -> None:
    url = "https://jobs.lever.co/palantir/575e0037-1234-4567-89ab-cdef01234567"
    api_url, hint = resolve_ats_endpoint(url)
    assert api_url == "https://api.lever.co/v0/postings/palantir/575e0037-1234-4567-89ab-cdef01234567"
    assert hint == "lever"


def test_resolve_ats_endpoint_ashby() -> None:
    url = "https://jobs.ashbyhq.com/linear/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    api_url, hint = resolve_ats_endpoint(url)
    assert api_url == "https://api.ashbyhq.com/posting-api/job-board/linear/job/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert hint == "ashby"


def test_resolve_ats_endpoint_generic() -> None:
    url = "https://careers.google.com/jobs/results/12345"
    api_url, hint = resolve_ats_endpoint(url)
    assert api_url == url
    assert hint == "generic"


class _MockHeaders:
    def __init__(self, headers_dict: dict[str, str]) -> None:
        self._headers = headers_dict

    def get(self, key: str, default: str = "") -> str:
        return self._headers.get(key, default)

    def get_content_charset(self) -> str | None:
        return "utf-8"


class _MockResponse:
    def __init__(self, content: bytes, content_type: str = "application/json") -> None:
        self._stream = io.BytesIO(content)
        self.headers = _MockHeaders({"Content-Type": content_type})

    def read(self) -> bytes:
        return self._stream.read()

    def __enter__(self) -> _MockResponse:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def test_http_raw_fetcher_success() -> None:
    def mock_urlopen(req: Any, timeout: float = 10.0) -> _MockResponse:
        assert timeout == 10.0
        return _MockResponse(b'{"title": "Staff Engineer"}', content_type="application/json")

    fetcher = HttpRawFetcher(urlopen_fn=mock_urlopen)
    payload = fetcher.fetch("https://boards.greenhouse.io/stripe/jobs/123")

    assert payload.url == "https://boards.greenhouse.io/stripe/jobs/123"
    assert payload.source_hint == "greenhouse"
    assert payload.content_type == "application/json"
    assert '{"title": "Staff Engineer"}' in payload.raw_content


def test_http_raw_fetcher_404_raises_value_error() -> None:
    def mock_urlopen(req: Any, timeout: float = 10.0) -> Any:
        raise urllib.error.HTTPError(
            url="https://example.com",
            code=404,
            msg="Not Found",
            hdrs=_MockHeaders({}),  # type: ignore[arg-type]
            fp=None,
        )

    fetcher = HttpRawFetcher(urlopen_fn=mock_urlopen)
    with pytest.raises(ValueError, match="Job posting not found or expired"):
        fetcher.fetch("https://example.com/job")


def test_http_raw_fetcher_timeout_raises_timeout_error() -> None:
    def mock_urlopen(req: Any, timeout: float = 10.0) -> Any:
        raise TimeoutError("Socket timed out")

    fetcher = HttpRawFetcher(urlopen_fn=mock_urlopen)
    with pytest.raises(TimeoutError, match="Connection timed out"):
        fetcher.fetch("https://example.com/job")


def test_http_raw_fetcher_invalid_protocol_raises() -> None:
    fetcher = HttpRawFetcher()
    with pytest.raises(ValueError, match="Invalid URL protocol"):
        fetcher.fetch("ftp://example.com/job")
