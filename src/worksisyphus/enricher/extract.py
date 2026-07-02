from __future__ import annotations

from dataclasses import dataclass
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from typing import Any
from urllib.parse import urlparse

from worksisyphus.enricher.schema import SCHEMA_VERSION


@dataclass(frozen=True)
class ExtractedDetail:
    status: str
    content_hash: str
    record: dict[str, Any]
    warnings: list[str]


def extract_jobright_detail(
    *,
    html: str,
    source_url: str,
    normalized_job: dict[str, Any],
    fetched_at: str,
    final_url: str | None = None,
) -> ExtractedDetail:
    scripts = _extract_scripts(html)
    job_posting = _json_or_none(scripts.get("job-posting")) or {}
    helper = _json_or_none(scripts.get("jobright-helper-job-detail-info")) or {}
    next_data = _json_or_none(scripts.get("__NEXT_DATA__")) or {}
    data_source = _get_path(next_data, ["props", "pageProps", "dataSource"]) or {}

    job_result = helper.get("jobResult") or data_source.get("jobResult") or {}
    company_result = helper.get("companyResult") or data_source.get("companyResult") or {}
    warnings: list[str] = []

    description_html = job_posting.get("description")
    description_text = _html_to_text(description_html) if description_html else None
    if not description_text:
        description_text = job_result.get("jobSummary")
    if not description_text:
        warnings.append("missing_description")

    active_status = _active_status(job_result)
    apply_url = _find_direct_apply_url(helper) or _find_direct_apply_url(data_source)
    if apply_url and _is_jobright_url(apply_url):
        apply_url = None

    record = {
        "schema_version": SCHEMA_VERSION,
        "identity": normalized_job.get("identity", {}),
        "source": {
            "listing_url": source_url,
            "final_url": final_url or source_url,
            "detail_source": "jobright_embedded_json",
            "fetched_at": fetched_at,
        },
        "status": {
            "fetch_status": "ok",
            "active_status": active_status,
            "is_deleted": job_result.get("isDeleted"),
            "valid_through": job_posting.get("validThrough"),
        },
        "company": {
            "name": (
                company_result.get("companyName")
                or _get_path(job_posting, ["hiringOrganization", "name"])
                or _get_path(normalized_job, ["company", "name"])
            ),
            "website_url": (
                company_result.get("companyURL")
                or _get_path(job_posting, ["hiringOrganization", "sameAs"])
                or _get_path(normalized_job, ["company", "website_url"])
            ),
            "size": company_result.get("companySize"),
            "description": company_result.get("companyDesc"),
            "categories": company_result.get("companyCategories"),
        },
        "role": {
            "title": job_result.get("jobTitle") or job_posting.get("title"),
            "normalized_title": job_result.get("jobNlpTitle"),
            "seniority": job_result.get("jobSeniority"),
            "employment_type": job_result.get("employmentType")
            or job_posting.get("employmentType"),
            "taxonomy": job_result.get("jobTaxonomyV3") or [],
        },
        "location": {
            "display": job_result.get("jobLocation"),
            "locations": job_result.get("jobLocations") or [],
            "country_code": job_result.get("countryCode"),
            "is_remote": job_result.get("isRemote"),
            "work_model": job_result.get("workModel"),
        },
        "compensation": {
            "salary_text": job_result.get("salaryDesc"),
            "min_salary": job_result.get("minSalary"),
            "max_salary": job_result.get("maxSalary"),
            "base_salary": job_posting.get("baseSalary"),
        },
        "description": {
            "summary": job_result.get("jobSummary"),
            "html": description_html,
            "text": description_text,
            "responsibilities": job_result.get("coreResponsibilities") or [],
            "must_have": _get_path(job_result, ["qualifications", "mustHave"]) or [],
            "preferred_have": _get_path(job_result, ["qualifications", "preferredHave"])
            or [],
            "skills": [item.get("skill") for item in job_result.get("jdCoreSkills", [])],
        },
        "application": {
            "source_listing_url": source_url,
            "direct_apply_url": apply_url,
            "is_company_site_link": job_result.get("isCompanySiteLink"),
        },
        "signals": {
            "min_years_experience": job_result.get("minYearsOfExperience"),
            "max_years_experience": job_result.get("maxYearsOfExperience"),
            "is_h1b_sponsor": job_result.get("isH1bSponsor"),
            "is_work_auth_required": job_result.get("isWorkAuthRequired"),
            "is_citizen_only": job_result.get("isCitizenOnly"),
            "is_clearance_required": job_result.get("isClearanceRequired"),
            "recommendation_tags": job_result.get("recommendationTags") or [],
        },
        "quality": {
            "warnings": warnings,
            "needs_review": bool(warnings),
        },
    }
    return ExtractedDetail(
        status="ok",
        content_hash=_hash_html(html),
        record=record,
        warnings=warnings,
    )


def _active_status(job_result: dict[str, Any]) -> str:
    if job_result.get("isDeleted") is True:
        return "closed"
    if job_result.get("isDeleted") is False:
        return "active"
    return "unknown"


def _hash_html(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def _json_or_none(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _get_path(payload: Any, path: list[str]) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _find_direct_apply_url(payload: Any) -> str | None:
    interesting_keys = {
        "applyurl",
        "applicationurl",
        "directapplyurl",
        "externalurl",
        "joburl",
        "sourceurl",
    }
    for key, value in _walk_json(payload):
        if key.lower() not in interesting_keys:
            continue
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return None


def _walk_json(payload: Any) -> list[tuple[str, Any]]:
    pairs: list[tuple[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            pairs.append((str(key), value))
            pairs.extend(_walk_json(value))
    elif isinstance(payload, list):
        for item in payload:
            pairs.extend(_walk_json(item))
    return pairs


def _is_jobright_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.netloc.lower().endswith("jobright.ai")


def _extract_scripts(html: str) -> dict[str, str]:
    parser = _ScriptParser()
    parser.feed(html)
    return parser.scripts


class _ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: dict[str, str] = {}
        self._current_key: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        attributes = dict(attrs)
        script_id = attributes.get("id")
        script_type = attributes.get("type")
        if script_id in {"job-posting", "jobright-helper-job-detail-info", "__NEXT_DATA__"}:
            self._current_key = script_id
            self._parts = []
        elif script_type == "application/ld+json":
            self._current_key = "ld+json"
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._current_key is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "script" or self._current_key is None:
            return
        self.scripts[self._current_key] = "".join(self._parts)
        self._current_key = None
        self._parts = []


def _html_to_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html)
    return parser.text()


class _TextParser(HTMLParser):
    BLOCK_TAGS = {"p", "br", "div", "ul", "ol"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            self.parts.append("\n- ")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(unescape(data))

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCK_TAGS or tag == "li":
            self.parts.append("\n")

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line)
