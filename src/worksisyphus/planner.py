"""Gemini JSON planner: job description + profile index in, validated Selection out.

Gemini only chooses IDs and an output name; it never writes resume text.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from .profile import Profile, planner_index
from .selection import Pick, Selection

GEMINI_MODEL_ID = "gemini-2.5-flash"
MAX_EXPERIENCES = 3
MAX_PROJECTS = 2
MAX_BULLETS = 4
MAX_SKILLS_PER_GROUP = 10

CallModel = Callable[[str], str]


class PlanError(ValueError):
    """Gemini returned something we refuse to render."""


def load_api_key(dotenv_path: Path = Path(".env")) -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key and dotenv_path.is_file():
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY") and "=" in line:
                key = line.split("=", 1)[1].strip().strip("'\"")
    if not key:
        raise PlanError("GEMINI_API_KEY is not set (environment or .env).")
    return key


def call_gemini(prompt: str, api_key: str, model_id: str = GEMINI_MODEL_ID, retries: int = 3) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    data = None
    for attempt in range(retries):
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            retryable = exc.code in (429, 500, 503) and attempt < retries - 1
            if not retryable:
                raise PlanError(f"Gemini HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:300]}") from exc
            time.sleep(2 ** (attempt + 1))
        except Exception as exc:
            if attempt == retries - 1:
                raise PlanError(f"Gemini request failed: {exc}") from exc
            time.sleep(2 ** (attempt + 1))
    candidates = data.get("candidates", [])
    if not candidates:
        raise PlanError(f"Gemini returned no candidates: {str(data)[:300]}")
    return str(candidates[0].get("content", {}).get("parts", [{}])[0].get("text", ""))


def _prompt(jd_text: str, profile: Profile) -> str:
    return f"""You tailor a resume by SELECTING from a fixed database. You never write or rewrite text.

Reply with ONLY a JSON object (no markdown fences, no commentary) shaped exactly like:
{{"name": "company_role", "experiences": [{{"id": "E1", "bullets": [1, 2]}}], "projects": [{{"id": "P2", "bullets": [1, 3]}}], "skills": {{"group_name": ["Skill A", "Skill B"]}}}}

Rules:
- "name": short lowercase snake_case output file name derived from the company and role.
- List experiences and projects most-relevant first; use only IDs from the database below.
- "bullets" are the 1-based bullet numbers under that item; pick the most relevant.
- At most {MAX_EXPERIENCES} experiences, {MAX_PROJECTS} projects, {MAX_BULLETS} bullets per item, {MAX_SKILLS_PER_GROUP} skills per group.
- Skills must be copied verbatim from the database, grouped under the same group names.

JOB DESCRIPTION:
{jd_text}

DATABASE:
{planner_index(profile)}
"""


def _parse_id(raw: object, prefix: str, count: int) -> int:
    match = re.fullmatch(rf"{prefix}(\d+)", str(raw).strip())
    if not match or not 1 <= int(match.group(1)) <= count:
        raise PlanError(f"Unknown {prefix}-item ID {raw!r}.")
    return int(match.group(1)) - 1


def _parse_picks(raw: object, prefix: str, items: tuple, max_items: int) -> tuple[Pick, ...]:
    if not isinstance(raw, list):
        raise PlanError(f"Expected a list for {prefix} selections.")
    picks: list[Pick] = []
    seen: set[int] = set()
    for entry in raw[:max_items]:
        if not isinstance(entry, dict):
            raise PlanError(f"Malformed {prefix} selection entry: {entry!r}.")
        index = _parse_id(entry.get("id"), prefix, len(items))
        if index in seen:
            raise PlanError(f"Duplicate item {prefix}{index + 1}.")
        seen.add(index)
        bullet_count = len(items[index].bullets)
        bullets: list[int] = []
        for num in entry.get("bullets", [])[:MAX_BULLETS]:
            if not isinstance(num, int) or not 1 <= num <= bullet_count:
                raise PlanError(f"Unknown bullet {num!r} for {prefix}{index + 1}.")
            if num - 1 not in bullets:
                bullets.append(num - 1)
        if not bullets:
            raise PlanError(f"No bullets selected for {prefix}{index + 1}.")
        picks.append(Pick(index=index, bullets=tuple(bullets)))
    if not picks:
        raise PlanError(f"Gemini selected no {prefix} items.")
    return tuple(picks)


def _parse_skills(raw: object, profile: Profile) -> dict[str, tuple[str, ...]]:
    if not isinstance(raw, dict):
        raise PlanError("Expected an object for skills.")
    skills: dict[str, tuple[str, ...]] = {}
    for group, items in raw.items():
        if group not in profile.skills:
            raise PlanError(f"Unknown skill group {group!r}.")
        known = set(profile.skills[group])
        chosen = [str(item) for item in items if str(item) in known][:MAX_SKILLS_PER_GROUP]
        if chosen:
            skills[group] = tuple(chosen)
    if not skills:
        raise PlanError("Gemini selected no valid skills.")
    return skills


def sanitize_name(raw: object) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(raw).lower()).strip("_")[:60]
    slug = slug or "tailored"
    return slug if slug.endswith("resume") else f"{slug}_resume"


def parse_plan(raw_text: str, profile: Profile) -> Selection:
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw_text.strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanError(f"Gemini did not return valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PlanError("Gemini did not return a JSON object.")
    return Selection(
        name=sanitize_name(data.get("name", "")),
        experiences=_parse_picks(data.get("experiences", []), "E", profile.experiences, MAX_EXPERIENCES),
        projects=_parse_picks(data.get("projects", []), "P", profile.projects, MAX_PROJECTS),
        skills=_parse_skills(data.get("skills", {}), profile),
    )


def plan_selection(jd_text: str, profile: Profile, call_model: CallModel | None = None) -> Selection:
    if call_model is None:
        api_key = load_api_key()
        call_model = lambda prompt: call_gemini(prompt, api_key)  # noqa: E731
    return parse_plan(call_model(_prompt(jd_text, profile)), profile)
