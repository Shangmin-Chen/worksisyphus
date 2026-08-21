"""Lint-style tests that verify plan/application consistency across the repo."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from worksisyphus.application import STATUSES

ROOT = Path(__file__).resolve().parents[1]
PLANS_DIR = ROOT / "plans"
APPLICATIONS_DIR = ROOT / "applications"


def _plan_slugs() -> set[str]:
    return {p.stem for p in PLANS_DIR.glob("*.json") if p.stem != "example"}


def _application_slugs() -> set[str]:
    slugs = set()
    if APPLICATIONS_DIR.is_dir():
        slugs |= {"_".join(d.name.split("_")[1:]) for d in APPLICATIONS_DIR.iterdir() if d.is_dir()}
    from worksisyphus.db import DEFAULT_DB_PATH, get_connection, list_applications_from_db

    if DEFAULT_DB_PATH.is_file():
        try:
            conn = get_connection(DEFAULT_DB_PATH)
            try:
                db_apps = list_applications_from_db(conn)
                slugs |= {"_".join(app["folder"].split("_")[1:]) for app in db_apps if "folder" in app}
            finally:
                conn.close()
        except Exception:
            pass
    return slugs


def test_every_plan_has_a_matching_application() -> None:
    application_slugs = _application_slugs()
    if not application_slugs:
        pytest.skip("Applications not present in filesystem or database")
    orphaned = _plan_slugs() - application_slugs
    assert orphaned == set(), f"Plans without matching applications: {sorted(orphaned)}"


def test_every_application_has_required_files() -> None:
    if not APPLICATIONS_DIR.is_dir() or not any(APPLICATIONS_DIR.iterdir()):
        pytest.skip("Applications directory not present or empty")
    missing: list[str] = []
    for d in sorted(APPLICATIONS_DIR.iterdir()):
        if not d.is_dir():
            continue
        for name in ("jd.txt", "meta.json", "Simon_Chen_Resume.pdf"):
            if not (d / name).is_file():
                missing.append(f"{d.name}/{name}")
    assert missing == [], f"Missing application files: {missing}"


def test_every_application_meta_json_is_valid() -> None:
    if not APPLICATIONS_DIR.is_dir() or not any(APPLICATIONS_DIR.iterdir()):
        pytest.skip("Applications directory not present or empty")
    invalid: list[str] = []
    for d in sorted(APPLICATIONS_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta_file = d / "meta.json"
        if not meta_file.is_file():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if not isinstance(meta, dict):
                invalid.append(f"{d.name}/meta.json is not a dict")
            elif "company" not in meta or not meta["company"]:
                invalid.append(f"{d.name}/meta.json missing company")
            elif meta.get("status") not in STATUSES:
                invalid.append(f"{d.name}/meta.json has invalid status {meta.get('status')!r}")
        except json.JSONDecodeError as exc:
            invalid.append(f"{d.name}/meta.json JSON error: {exc}")
    assert invalid == [], f"Invalid meta.json files: {invalid}"
