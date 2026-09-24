"""Universal HTTP fetcher using standard library urllib."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ....core.domain.ingestion import RawJobPayload
from ....ports.ingestion import RawFetcherPort

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


class HttpRawFetcher(RawFetcherPort):
    """Fetches raw web content over HTTP/HTTPS with standard browser headers."""

    def __init__(self, urlopen_fn: Callable[..., Any] | None = None) -> None:
        self._urlopen = urlopen_fn or urllib.request.urlopen

    def fetch(self, url: str, timeout: float = 10.0) -> RawJobPayload:
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError(f"Invalid URL protocol: '{url}' (must be http:// or https://)")

        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)

        try:
            with self._urlopen(req, timeout=timeout) as response:
                content_bytes = response.read()
                content_type = response.headers.get("Content-Type", "text/html")
                charset = response.headers.get_content_charset() or "utf-8"
                raw_text = content_bytes.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            raise ValueError(f"Job posting not found or expired at {url} (HTTP {exc.code})") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TimeoutError(f"Connection timed out fetching {url} after {timeout}s") from exc
            raise ValueError(f"Failed to fetch {url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise TimeoutError(f"Connection timed out fetching {url} after {timeout}s") from exc

        return RawJobPayload(
            url=url,
            raw_content=raw_text,
            content_type=content_type,
            source_hint="web",
            fetched_at=datetime.now(UTC).isoformat(),
        )
