"""ETL posting compiler transforming raw job payloads into normalized JobPosting entities."""

from __future__ import annotations

import html
import json
import re
import urllib.parse
from typing import Any

from ....core.domain.ingestion import JobPosting, RawJobPayload, ScreeningQuestion
from ....ports.ingestion import JobTransformerPort
from .pre_cleaner import clean_html


def _extract_company_from_url(url: str) -> str:
    """Best-effort extraction of company name from posting URL."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if parsed.scheme == "file" or not host:
        file_name = path.split("/")[-1].split(".")[0]
        for prefix in ("greenhouse_", "lever_", "ashby_"):
            if file_name.lower().startswith(prefix):
                return file_name[len(prefix) :].replace("-", " ").replace("_", " ").title()
        if file_name and file_name not in ("current_jd", "raw_payload"):
            return file_name.replace("-", " ").replace("_", " ").title()
        return ""

    # Subdomain or path on ATS domains
    if "greenhouse.io" in host:
        m = re.search(r"(?:boards|job-boards)\.greenhouse\.io/([^/]+)", url)
        if m:
            return m.group(1).replace("-", " ").title()
        m = re.search(r"greenhouse\.io/([^/]+)", path)
        if m:
            return m.group(1).replace("-", " ").title()

    if "lever.co" in host:
        parts = path.split("/")
        if len(parts) >= 1 and parts[0]:
            return parts[0].replace("-", " ").title()

    if "ashbyhq.com" in host:
        parts = path.split("/")
        if len(parts) >= 1 and parts[0]:
            return parts[0].replace("-", " ").title()

    # Generic host: careers.company.com or company.com
    host_parts = host.split(".")
    if len(host_parts) >= 2:
        candidate = host_parts[-2] if host_parts[-1] in ("com", "org", "net", "io", "co") else host_parts[0]
        if candidate in ("careers", "jobs", "boards"):
            candidate = host_parts[-3] if len(host_parts) >= 3 else host_parts[0]
        return candidate.replace("-", " ").title()

    return ""


def _extract_json_ld(raw_html: str) -> dict[str, Any] | None:
    """Extract schema.org JobPosting JSON-LD object if present in HTML."""
    matches = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        raw_html,
        re.DOTALL | re.IGNORECASE,
    )
    for block in matches:
        try:
            data = json.loads(block.strip())
            if isinstance(data, dict):
                if data.get("@type") == "JobPosting":
                    return data
                # Sometimes wrapped in @graph
                if "@graph" in data and isinstance(data["@graph"], list):
                    for item in data["@graph"]:
                        if isinstance(item, dict) and item.get("@type") == "JobPosting":
                            return item
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        return item
        except Exception:
            continue
    return None


def _extract_meta_tag(raw_html: str, property_name: str) -> str:
    """Extract content from an OpenGraph or meta tag."""
    patterns = [
        rf'<meta[^>]*property=["\']{re.escape(property_name)}["\'][^>]*content=["\']([^"\']+)["\']',
        rf'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']{re.escape(property_name)}["\']',
        rf'<meta[^>]*name=["\']{re.escape(property_name)}["\'][^>]*content=["\']([^"\']+)["\']',
        rf'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']{re.escape(property_name)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_html, re.IGNORECASE)
        if match:
            return html.unescape(match.group(1).strip())
    return ""


class EtlJobTransformer(JobTransformerPort):
    """Compiles raw job payloads (Greenhouse, Lever, Ashby, or HTML) into JobPosting entities."""

    def transform(
        self,
        raw: RawJobPayload,
        company_override: str = "",
        role_override: str = "",
    ) -> JobPosting:
        company = company_override.strip()
        role = role_override.strip()
        location = ""
        jd_text = ""
        screening_questions: list[ScreeningQuestion] = []
        raw_dict: dict[str, Any] = {}

        if raw.content_type == "application/json":
            try:
                raw_dict = json.loads(raw.raw_content)
            except Exception as exc:
                raise ValueError(f"Malformed JSON payload from {raw.url}: {exc}") from exc

            if raw.source_hint == "greenhouse" or "questions" in raw_dict:
                company, role, location, jd_text, screening_questions = self._transform_greenhouse(
                    raw, raw_dict, company, role
                )
            elif raw.source_hint == "lever" or ("categories" in raw_dict and "descriptionPlain" in raw_dict):
                company, role, location, jd_text, screening_questions = self._transform_lever(
                    raw, raw_dict, company, role
                )
            elif raw.source_hint == "ashby" or "descriptionHtml" in raw_dict:
                company, role, location, jd_text, screening_questions = self._transform_ashby(
                    raw, raw_dict, company, role
                )
            else:
                # Generic JSON
                company, role, location, jd_text = self._transform_generic_json(raw, raw_dict, company, role)
        else:
            # HTML payload
            company, role, location, jd_text, screening_questions = self._transform_html(raw, company, role)

        # Fallbacks if still unset
        if not company:
            company = _extract_company_from_url(raw.url) or "Unknown Company"
        if not role:
            role = "Software Engineer"
        if not jd_text:
            jd_text = clean_html(raw.raw_content)

        return JobPosting(
            company=company,
            role=role,
            jd_text=jd_text,
            url=raw.url,
            location=location,
            source_type=raw.source_hint,
            screening_questions=tuple(screening_questions),
            raw_payload=raw_dict if raw_dict else {"raw_content_length": len(raw.raw_content)},
        )

    def _transform_greenhouse(
        self,
        raw: RawJobPayload,
        data: dict[str, Any],
        company: str,
        role: str,
    ) -> tuple[str, str, str, str, list[ScreeningQuestion]]:
        if not role:
            role = data.get("title", "").strip()
        if not company:
            company = str(data.get("company_name", "") or data.get("company", "")).strip() or _extract_company_from_url(
                raw.url
            )

        loc_data = data.get("location")
        location = loc_data.get("name", "") if isinstance(loc_data, dict) else ""

        # Content is unescaped HTML
        raw_html = data.get("content", "")
        jd_text = clean_html(raw_html)

        # Extract screening questions
        questions: list[ScreeningQuestion] = []
        for i, q in enumerate(data.get("questions", [])):
            if not isinstance(q, dict):
                continue
            prompt = clean_html(q.get("label", "") or q.get("name", ""))
            if not prompt:
                continue
            q_id = str(q.get("id") or q.get("name") or f"q_{i + 1}")
            fields = q.get("fields", [])
            q_type = "text"
            options: list[str] = []

            if fields and isinstance(fields, list) and isinstance(fields[0], dict):
                f_type = fields[0].get("type", "")
                if f_type in ("input_text", "text"):
                    q_type = "text"
                elif f_type in ("textarea", "text_area"):
                    q_type = "textarea"
                elif f_type in ("multi_value_single_select", "select"):
                    q_type = "select"
                    for val in fields[0].get("values", []):
                        if isinstance(val, dict) and "label" in val:
                            options.append(str(val["label"]))
                elif f_type in ("attachment", "file"):
                    q_type = "file"
                elif f_type == "boolean":
                    q_type = "boolean"

            required = bool(q.get("required", False))
            questions.append(
                ScreeningQuestion(
                    question_id=q_id,
                    prompt=prompt,
                    question_type=q_type,
                    required=required,
                    options=tuple(options),
                )
            )

        return company, role, location, jd_text, questions

    def _transform_lever(
        self,
        raw: RawJobPayload,
        data: dict[str, Any],
        company: str,
        role: str,
    ) -> tuple[str, str, str, str, list[ScreeningQuestion]]:
        if not role:
            role = data.get("text", "").strip()
        categories = data.get("categories", {})
        if not company:
            company = str(
                data.get("company", "") or (categories.get("team", "") if isinstance(categories, dict) else "")
            ).strip() or _extract_company_from_url(raw.url)
        location = categories.get("location", "") if isinstance(categories, dict) else ""

        # Build complete JD text
        parts: list[str] = []
        desc = data.get("description", "") or data.get("descriptionPlain", "")
        if desc:
            parts.append(clean_html(desc))

        lists = data.get("lists", [])
        if isinstance(lists, list):
            for item in lists:
                if isinstance(item, dict):
                    title = item.get("text", "")
                    content = item.get("content", "")
                    if title:
                        parts.append(f"\n{title}:")
                    if content:
                        parts.append(clean_html(content))

        additional = data.get("additional", "") or data.get("additionalPlain", "")
        if additional:
            parts.append(clean_html(additional))

        jd_text = "\n\n".join(p for p in parts if p.strip()).strip()

        # Screening questions
        questions: list[ScreeningQuestion] = []
        custom_questions = data.get("customQuestions", [])
        if isinstance(custom_questions, list):
            for i, q in enumerate(custom_questions):
                if not isinstance(q, dict):
                    continue
                prompt = clean_html(q.get("text", ""))
                if not prompt:
                    continue
                q_id = str(q.get("id") or f"lever_q_{i + 1}")
                q_type = "text"
                field_type = q.get("type", "")
                if field_type in ("multiple-choice", "dropdown"):
                    q_type = "select"
                elif field_type == "text-area":
                    q_type = "textarea"
                elif field_type == "file":
                    q_type = "file"

                options: list[str] = []
                for opt in q.get("options", []):
                    if isinstance(opt, dict) and "text" in opt:
                        options.append(str(opt["text"]))
                    elif isinstance(opt, str):
                        options.append(opt)

                questions.append(
                    ScreeningQuestion(
                        question_id=q_id,
                        prompt=prompt,
                        question_type=q_type,
                        required=bool(q.get("required", False)),
                        options=tuple(options),
                    )
                )

        return company, role, location, jd_text, questions

    def _transform_ashby(
        self,
        raw: RawJobPayload,
        data: dict[str, Any],
        company: str,
        role: str,
    ) -> tuple[str, str, str, str, list[ScreeningQuestion]]:
        if not role:
            role = (data.get("title") or data.get("jobTitle") or "").strip()
        if not company:
            company = data.get("organizationName") or _extract_company_from_url(raw.url)

        location = str(data.get("locationName") or data.get("location") or "")

        desc = data.get("descriptionHtml") or data.get("descriptionPlain") or ""
        jd_text = clean_html(desc)

        return company, role, location, jd_text, []

    def _transform_generic_json(
        self,
        raw: RawJobPayload,
        data: dict[str, Any],
        company: str,
        role: str,
    ) -> tuple[str, str, str, str]:
        if not role:
            role = str(data.get("title") or data.get("role") or "Software Engineer").strip()
        if not company:
            company = str(data.get("company") or data.get("organization") or _extract_company_from_url(raw.url)).strip()

        location = str(data.get("location") or "")
        desc = str(data.get("description") or data.get("content") or data.get("jd") or "")
        jd_text = clean_html(desc) if desc else json.dumps(data, indent=2)

        return company, role, location, jd_text

    def _transform_html(
        self,
        raw: RawJobPayload,
        company: str,
        role: str,
    ) -> tuple[str, str, str, str, list[ScreeningQuestion]]:
        location = ""
        raw_html = raw.raw_content

        # 1. Try schema.org JobPosting JSON-LD
        json_ld = _extract_json_ld(raw_html)
        if json_ld:
            if not role:
                role = str(json_ld.get("title", "")).strip()
            if not company:
                hiring_org = json_ld.get("hiringOrganization")
                if isinstance(hiring_org, dict):
                    company = str(hiring_org.get("name", "")).strip()
            loc_val = json_ld.get("jobLocation")
            if isinstance(loc_val, dict):
                address = loc_val.get("address")
                if isinstance(address, dict):
                    locality = address.get("addressLocality", "")
                    region = address.get("addressRegion", "")
                    location = f"{locality}, {region}".strip(", ")

            desc_html = json_ld.get("description", "")
            if desc_html:
                jd_text = clean_html(desc_html)
                return company, role, location, jd_text, []

        # 2. Try OpenGraph meta tags
        if not role:
            og_title = _extract_meta_tag(raw_html, "og:title")
            if og_title:
                # Often "Software Engineer at Company" or "Software Engineer - Company"
                role_match = re.split(r"\s+(?:at|[-|\u2013\u2014])\s+", og_title)
                role = role_match[0].strip()
                if not company and len(role_match) > 1:
                    company = role_match[1].strip()

        if not company:
            og_site_name = _extract_meta_tag(raw_html, "og:site_name")
            if og_site_name:
                company = og_site_name.strip()

        # 3. Try <title> tag
        if not role or not company:
            title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
            if title_match:
                title_text = html.unescape(title_match.group(1).strip())
                title_parts = re.split(r"\s+(?:at|[-|\u2013\u2014])\s+", title_text)
                if not role and title_parts:
                    role = title_parts[0].strip()
                if not company and len(title_parts) > 1:
                    company = title_parts[-1].strip()

        # Clean entire HTML for JD text
        jd_text = clean_html(raw_html)
        return company, role, location, jd_text, []
