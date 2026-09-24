"""Unit tests for HttpRawFetcher."""

from __future__ import annotations

import io
import urllib.error
from typing import Any

import pytest

from worksisyphus.adapters.outbound.ingestion.http_fetcher import HttpRawFetcher


class _MockHeaders:
    def __init__(self, headers_dict: dict[str, str]) -> None:
        self._headers = headers_dict

    def get(self, key: str, default: str = "") -> str:
        return self._headers.get(key, default)

    def get_content_charset(self) -> str | None:
        return "utf-8"


class _MockResponse:
    def __init__(self, content: bytes, content_type: str = "text/html") -> None:
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
        return _MockResponse(b"<h1>Software Engineer</h1><p>We are hiring.</p>")

    fetcher = HttpRawFetcher(urlopen_fn=mock_urlopen)
    payload = fetcher.fetch("https://stripe.com/jobs/123")

    assert payload.url == "https://stripe.com/jobs/123"
    assert "Software Engineer" in payload.raw_content
    assert payload.content_type == "text/html"


def test_http_raw_fetcher_404_raises_value_error() -> None:
    def mock_urlopen(req: Any, timeout: float = 10.0) -> Any:
        raise urllib.error.HTTPError(
            url="https://example.com/job",
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
