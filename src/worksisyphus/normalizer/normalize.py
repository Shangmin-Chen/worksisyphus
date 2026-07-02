from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from urllib.parse import urlparse, urlunparse

from worksisyphus.normalizer.schema import SCHEMA_VERSION

WORK_MODEL_MAP = {
    "hybrid": "hybrid",
    "on site": "onsite",
    "onsite": "onsite",
    "on-site": "onsite",
    "remote": "remote",
}

MONTH_FORMATS = ("%b %d", "%B %d")


def normalize_payload(payload: dict) -> list[dict]:
    observed_at = _parse_observed_at(payload.get("observed_at"))
    normalized = [
        normalize_record(record, observed_at=observed_at)
        for record in payload.get("records", [])
    ]
    return sorted(normalized, key=lambda item: item["identity"]["canonical_id"])


def normalize_record(record: dict, *, observed_at: datetime | None) -> dict:
    extracted = record.get("extracted", {})
    source = record.get("source", {})
    warnings: list[str] = []

    source_name = _clean(source.get("name"))
    source_key = _clean(record.get("key"))
    company_name = _clean(extracted.get("company"))
    company_url = _clean_url(extracted.get("company_url"))
    job_title = _clean(extracted.get("job_title"))
    source_listing_url = _clean_url(extracted.get("job_url"))
    jobright_id = _clean(extracted.get("jobright_id"))
    location_raw = _clean(extracted.get("location"))
    work_model_raw = _clean(extracted.get("work_model"))
    date_posted_raw = _clean(extracted.get("date_posted"))

    if not company_name:
        warnings.append("missing_company")
    if not job_title:
        warnings.append("missing_job_title")
    if not source_listing_url:
        warnings.append("missing_source_listing_url")

    posted_date = _normalize_posted_date(date_posted_raw, observed_at)
    if date_posted_raw and posted_date is None:
        warnings.append("unparsed_date_posted")

    workplace_type = _normalize_work_model(work_model_raw)
    if work_model_raw and workplace_type == "unknown":
        warnings.append("unknown_work_model")

    canonical_id = _canonical_id(
        source_name=source_name,
        source_key=source_key,
        jobright_id=jobright_id,
        source_listing_url=source_listing_url,
    )
    dedupe_key = _dedupe_key(
        company_name=company_name,
        job_title=job_title,
        location=location_raw,
        source_listing_url=source_listing_url,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "canonical_id": canonical_id,
            "dedupe_key": dedupe_key,
            "source_record_key": source_key,
            "source_job_id": jobright_id,
        },
        "company": {
            "name": company_name,
            "website_url": company_url,
        },
        "role": {
            "title": job_title,
        },
        "locations": _normalize_locations(location_raw),
        "workplace": {
            "type": workplace_type,
            "raw": work_model_raw,
        },
        "posted": {
            "raw": date_posted_raw,
            "date": posted_date.isoformat() if posted_date else None,
            "inferred_from_observed_at": bool(posted_date and observed_at),
        },
        "application": {
            "source_listing_url": source_listing_url,
            "direct_apply_url": None,
        },
        "source": {
            "name": source_name,
            "repo": _clean_url(source.get("repo")),
            "branch": _clean(source.get("branch")),
            "path": _clean(source.get("path")),
            "commit": _clean(source.get("commit")),
            "row_number": source.get("row_number"),
        },
        "quality": {
            "warnings": warnings,
            "needs_review": bool(warnings),
        },
    }


def _canonical_id(
    *,
    source_name: str | None,
    source_key: str | None,
    jobright_id: str | None,
    source_listing_url: str | None,
) -> str:
    if jobright_id:
        basis = f"jobright:{jobright_id}"
    elif source_listing_url:
        basis = f"url:{source_listing_url}"
    else:
        basis = f"source:{source_name or 'unknown'}:{source_key or 'unknown'}"
    return _hash("job", basis)


def _dedupe_key(
    *,
    company_name: str | None,
    job_title: str | None,
    location: str | None,
    source_listing_url: str | None,
) -> str:
    parsed = urlparse(source_listing_url or "")
    url_path = parsed.path.rstrip("/")
    parts = [
        _normalize_for_key(company_name),
        _normalize_for_key(job_title),
        _normalize_for_key(location),
        _normalize_for_key(url_path),
    ]
    return _hash("dedupe", "|".join(parts))


def _normalize_locations(location_raw: str | None) -> list[dict]:
    if not location_raw:
        return []
    return [
        {
            "display": location_raw,
            "raw": location_raw,
        }
    ]


def _normalize_work_model(work_model_raw: str | None) -> str:
    if not work_model_raw:
        return "unknown"
    return WORK_MODEL_MAP.get(_normalize_for_key(work_model_raw), "unknown")


def _normalize_posted_date(
    date_posted_raw: str | None,
    observed_at: datetime | None,
) -> date | None:
    if not date_posted_raw:
        return None
    if observed_at is None:
        return None

    for date_format in MONTH_FORMATS:
        try:
            parsed = datetime.strptime(date_posted_raw, date_format)
            break
        except ValueError:
            parsed = None
    if parsed is None:
        return None

    observed_date = observed_at.date()
    candidate = date(observed_date.year, parsed.month, parsed.day)
    if candidate > observed_date + timedelta(days=1):
        candidate = date(observed_date.year - 1, parsed.month, parsed.day)
    return candidate


def _parse_observed_at(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _clean_url(value: object) -> str | None:
    text = _clean(value)
    if not text:
        return None
    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return text
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            "",
            parsed.query,
            "",
        )
    )


def _normalize_for_key(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _hash(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"
