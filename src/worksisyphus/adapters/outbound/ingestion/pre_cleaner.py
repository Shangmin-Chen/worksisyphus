"""HTML pre-cleaner and noise removal for job postings."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

IGNORED_TAGS = frozenset(
    {
        "script",
        "style",
        "svg",
        "noscript",
        "nav",
        "footer",
        "header",
        "iframe",
        "head",
        "select",
        "button",
    }
)

BLOCK_TAGS = frozenset(
    {
        "p",
        "div",
        "section",
        "article",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
        "tr",
        "ul",
        "ol",
    }
)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in IGNORED_TAGS:
            self._ignore_depth += 1
            return

        if self._ignore_depth > 0:
            return

        if tag_lower in BLOCK_TAGS:
            self._pieces.append("\n\n")
        elif tag_lower == "br":
            self._pieces.append("\n")
        elif tag_lower == "li":
            self._pieces.append("\n• ")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in IGNORED_TAGS:
            if self._ignore_depth > 0:
                self._ignore_depth -= 1
            return

        if self._ignore_depth > 0:
            return

        if tag_lower in BLOCK_TAGS:
            self._pieces.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignore_depth == 0:
            self._pieces.append(data)

    def get_text(self) -> str:
        return "".join(self._pieces)


class PreCleaner:
    """Pre-cleans raw HTML or text, removing script/style noise and normalizing whitespace."""

    def clean(self, raw_content: str) -> str:
        """Strip markup noise, preserve paragraph and bullet layout, unescape entities."""
        if not raw_content:
            return ""

        # Quick check: if there are no HTML tags, just normalize whitespace
        if "<" not in raw_content or ">" not in raw_content:
            return self._normalize_text(html.unescape(raw_content))

        parser = _HTMLTextExtractor()
        try:
            parser.feed(raw_content)
            extracted = parser.get_text()
        except Exception:
            # Fallback regex strip if parser encounters malformed HTML
            extracted = re.sub(r"<[^>]+>", " ", raw_content)

        unescaped = html.unescape(extracted)
        return self._normalize_text(unescaped)

    def _normalize_text(self, text: str) -> str:
        # Standardize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Replace non-breaking spaces and unicode spaces
        text = text.replace("\xa0", " ").replace("\u200b", "")

        # Normalize line-by-line whitespace
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        cleaned = "\n".join(lines)

        # Collapse more than 2 consecutive newlines into 2
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()


def clean_html(raw_content: str) -> str:
    """Convenience helper to pre-clean raw HTML content."""
    return PreCleaner().clean(raw_content)
