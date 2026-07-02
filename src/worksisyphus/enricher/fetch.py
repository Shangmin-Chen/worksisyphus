from __future__ import annotations

from dataclasses import dataclass
import urllib.error
import urllib.request


@dataclass(frozen=True)
class FetchResult:
    url: str
    status_code: int | None
    body: str | None
    error: str | None


def fetch_html(url: str, *, timeout: int = 30) -> FetchResult:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Mozilla/5.0 (compatible; WorkSisyphus/0.1)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return FetchResult(
                url=response.geturl(),
                status_code=response.status,
                body=response.read().decode(charset, errors="replace"),
                error=None,
            )
    except urllib.error.HTTPError as exc:
        return FetchResult(
            url=url,
            status_code=exc.code,
            body=None,
            error=f"HTTP {exc.code}: {exc.reason}",
        )
    except OSError as exc:
        return FetchResult(url=url, status_code=None, body=None, error=str(exc))
