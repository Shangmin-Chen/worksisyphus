"""HTTP raw posting fetcher using standard library urllib."""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
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
    "Accept": "application/json, text/html, application/xhtml+xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def resolve_ats_endpoint(url: str) -> tuple[str, str]:
    """Detect if URL points to a known ATS with a public JSON API.

    Returns:
        (resolved_fetch_url, source_hint)
    """
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path

    # Greenhouse
    # e.g., https://boards.greenhouse.io/stripe/jobs/12345
    # or https://job-boards.greenhouse.io/stripe/jobs/12345
    if "greenhouse.io" in host:
        gh_match = re.search(r"/(?:embed/job_app\?for=)?([^/]+)/jobs/(\d+)", path)
        if gh_match:
            company, job_id = gh_match.group(1), gh_match.group(2)
            api_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}?questions=true"
            return api_url, "greenhouse"

    # Lever
    # e.g., https://jobs.lever.co/palantir/575e0037-1234-4567-89ab-cdef01234567
    if "lever.co" in host:
        lever_match = re.search(r"/([^/]+)/([a-f0-9\-]+)", path)
        if lever_match:
            company, job_id = lever_match.group(1), lever_match.group(2)
            api_url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
            return api_url, "lever"

    # Ashby
    # e.g., https://jobs.ashbyhq.com/linear/575e0037-1234-4567-89ab-cdef01234567
    if "ashbyhq.com" in host:
        ashby_match = re.search(r"/([^/]+)/([a-f0-9\-]+)", path)
        if ashby_match:
            company, job_id = ashby_match.group(1), ashby_match.group(2)
            api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company}/job/{job_id}"
            return api_url, "ashby"

    return url, "generic"


class HttpRawFetcher(RawFetcherPort):
    """Fetches job postings over HTTP/HTTPS with ATS API auto-routing."""

    def __init__(
        self,
        urlopen_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._urlopen = urlopen_fn or urllib.request.urlopen

    def fetch(self, url: str, timeout: float = 10.0) -> RawJobPayload:
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError(f"Invalid URL protocol: '{url}' (must be http:// or https://)")

        fetch_url, source_hint = resolve_ats_endpoint(url)
        req = urllib.request.Request(fetch_url, headers=DEFAULT_HEADERS)

        try:
            with self._urlopen(req, timeout=timeout) as response:
                content_bytes = response.read()
                content_type = response.headers.get("Content-Type", "")
                charset = response.headers.get_content_charset() or "utf-8"
                raw_text = content_bytes.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            # If Ashby JSON API fails (e.g., 404), try falling back to the original HTML page
            if source_hint == "ashby" and fetch_url != url:
                fallback_req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
                try:
                    with self._urlopen(fallback_req, timeout=timeout) as response:
                        content_bytes = response.read()
                        content_type = response.headers.get("Content-Type", "text/html")
                        charset = response.headers.get_content_charset() or "utf-8"
                        raw_text = content_bytes.decode(charset, errors="replace")
                        source_hint = "generic"
                except Exception:
                    raise ValueError(f"Job posting not found or expired at {url} (HTTP {exc.code})") from exc
            else:
                raise ValueError(f"Job posting not found or expired at {url} (HTTP {exc.code})") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TimeoutError(f"Connection timed out fetching {url} after {timeout}s") from exc
            raise ValueError(f"Failed to fetch {url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise TimeoutError(f"Connection timed out fetching {url} after {timeout}s") from exc

        # Determine normalized content_type
        if "application/json" in content_type or (raw_text.strip().startswith("{") and raw_text.strip().endswith("}")):
            normalized_content_type = "application/json"
        else:
            normalized_content_type = "text/html"

        return RawJobPayload(
            url=url,
            raw_content=raw_text,
            content_type=normalized_content_type,
            source_hint=source_hint,
            fetched_at=datetime.now(UTC).isoformat(),
        )
