from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from typing import Iterable

from worksisyphus.aggregator.config import GitHubReadmeSource

TABLE_HEADER = ["Company", "Job Title", "Location", "Work Model", "Date Posted"]
TAG_RE = re.compile(r"<[^>]+>")
JOBRIGHT_ID_RE = re.compile(r"/jobs/info/([^/?#]+)")


@dataclass(frozen=True)
class ParsedLink:
    text: str | None
    url: str | None


def parse_jobright_readme(
    readme: str,
    *,
    source: GitHubReadmeSource,
    commit_sha: str,
) -> list[dict]:
    records: list[dict] = []
    current_company_text: str | None = None
    current_company_url: str | None = None

    for row_number, cells in _iter_markdown_table_rows(readme.splitlines()):
        if cells == TABLE_HEADER:
            continue
        if _is_separator_row(cells):
            continue
        if len(cells) != len(TABLE_HEADER):
            continue

        company_cell, title_cell, location_cell, work_model_cell, date_cell = cells
        company_link = _extract_first_link(company_cell)
        title_link = _extract_first_link(title_cell)
        continuation = _clean_text(company_cell) == "\u21b3"

        if not continuation:
            current_company_text = company_link.text or _clean_text(company_cell)
            current_company_url = company_link.url

        company_text = current_company_text if continuation else (
            company_link.text or _clean_text(company_cell)
        )
        company_url = current_company_url if continuation else company_link.url
        job_title = title_link.text or _clean_text(title_cell)
        job_url = title_link.url
        jobright_id = _extract_jobright_id(job_url)
        listing_key = _listing_key(source.slug, job_url, row_number)

        records.append(
            {
                "source": {
                    "name": source.slug,
                    "repo": source.repo_url,
                    "branch": source.branch,
                    "path": source.path,
                    "commit": commit_sha,
                    "row_number": row_number,
                },
                "key": listing_key,
                "raw": {
                    "company": company_cell,
                    "job_title": title_cell,
                    "location": location_cell,
                    "work_model": work_model_cell,
                    "date_posted": date_cell,
                },
                "extracted": {
                    "company": company_text,
                    "company_url": company_url,
                    "is_company_continuation": continuation,
                    "job_title": job_title,
                    "job_url": job_url,
                    "jobright_id": jobright_id,
                    "location": _clean_text(location_cell),
                    "work_model": _clean_text(work_model_cell),
                    "date_posted": _clean_text(date_cell),
                },
            }
        )

    return records


def _iter_markdown_table_rows(lines: Iterable[str]) -> Iterable[tuple[int, list[str]]]:
    in_daily_table = False
    in_table = False

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("| Company | Job Title | Location |"):
            in_daily_table = True
            in_table = True

        if not in_table:
            continue

        if not stripped.startswith("|"):
            if in_daily_table:
                break
            continue

        yield line_number, [_clean_cell(cell) for cell in _split_markdown_row(stripped)]


def _split_markdown_row(row: str) -> list[str]:
    trimmed = row.strip().strip("|")
    return [cell.strip() for cell in trimmed.split("|")]


def _clean_cell(cell: str) -> str:
    return html.unescape(cell.strip())


def _clean_text(value: str) -> str:
    without_tags = TAG_RE.sub("", value)
    without_markup = (
        without_tags.replace("**", "")
        .replace("__", "")
        .replace("<br>", " ")
        .replace("<br/>", " ")
        .replace("<br />", " ")
    )
    link = _extract_first_link(without_markup)
    if link.text:
        return _collapse_whitespace(link.text)
    return _collapse_whitespace(without_markup)


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _extract_first_link(value: str) -> ParsedLink:
    for start, char in enumerate(value):
        if char != "[":
            continue

        bracket_depth = 0
        for index in range(start + 1, len(value)):
            current = value[index]
            if current == "[":
                bracket_depth += 1
                continue
            if current != "]":
                continue
            if bracket_depth > 0:
                bracket_depth -= 1
                continue
            if index + 1 >= len(value) or value[index + 1] != "(":
                continue

            close_paren = value.find(")", index + 2)
            if close_paren == -1:
                continue
            return ParsedLink(
                text=_collapse_whitespace(value[start + 1 : index]),
                url=value[index + 2 : close_paren],
            )

    return ParsedLink(text=None, url=None)


def _extract_jobright_id(url: str | None) -> str | None:
    if not url:
        return None
    match = JOBRIGHT_ID_RE.search(url)
    if not match:
        return None
    return match.group(1)


def _listing_key(source_slug: str, job_url: str | None, row_number: int) -> str:
    stable_value = job_url or f"row:{row_number}"
    digest = hashlib.sha256(f"{source_slug}:{stable_value}".encode("utf-8")).hexdigest()
    return digest[:24]


def _is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    return all(set(cell.replace(" ", "")) <= {"-"} for cell in cells)
