"""Lint-style tests that verify application and DB consistency across the repo."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from worksisyphus.application import STATUSES

ROOT = Path(__file__).resolve().parents[1]
APPLICATIONS_DIR = ROOT / "applications"


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


def test_applications_db_and_filesystem_consistency() -> None:
    from worksisyphus.db import DEFAULT_DB_PATH, get_connection, list_applications_from_db

    if not DEFAULT_DB_PATH.is_file() or not APPLICATIONS_DIR.is_dir() or not any(APPLICATIONS_DIR.iterdir()):
        pytest.skip("Database or applications directory not present")

    conn = get_connection(DEFAULT_DB_PATH)
    try:
        db_apps = {app["folder"] for app in list_applications_from_db(conn)}
    finally:
        conn.close()

    fs_apps = {d.name for d in APPLICATIONS_DIR.iterdir() if d.is_dir()}
    diff = fs_apps.symmetric_difference(db_apps)
    assert diff == set(), f"Inconsistency between applications/ and DB: {diff}"
