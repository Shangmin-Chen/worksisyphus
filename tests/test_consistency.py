"""Lint-style tests that verify application and DB consistency across the repo."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from worksisyphus.application import STATUSES

ROOT = Path(__file__).resolve().parents[1]
APPLICATIONS_DIR = ROOT / "applications"
PLANS_DIR = ROOT / "plans"
DRAFTS_DIR = PLANS_DIR / "drafts"


def _plan_stems() -> set[str]:
    """Every plan that claims to correspond to a real application.

    plans/drafts/ is the escape hatch for work in progress; anything directly in plans/ is
    asserted to have been applied with, so a plan cannot silently drift out of the record.
    """
    return {p.stem for p in PLANS_DIR.glob("*.json") if p.stem != "example"}


def _application_stems() -> set[str]:
    """Application identifiers minus their date prefix, from the filesystem and the database.

    Both sources are consulted because applications/ and worksisyphus.db are gitignored: a
    developer may have either, both, or neither, and the check should run whenever one exists.
    """
    stems: set[str] = set()
    if APPLICATIONS_DIR.is_dir():
        stems |= {"_".join(d.name.split("_")[1:]) for d in APPLICATIONS_DIR.iterdir() if d.is_dir()}

    from worksisyphus.db import DEFAULT_DB_PATH, get_connection, list_applications_from_db

    if DEFAULT_DB_PATH.is_file():
        conn = get_connection(DEFAULT_DB_PATH)
        try:
            stems |= {"_".join(app["folder"].split("_")[1:]) for app in list_applications_from_db(conn)}
        finally:
            conn.close()
    return stems


def test_every_plan_has_a_matching_application() -> None:
    """A plan in plans/ must correspond to an application; drafts belong in plans/drafts/."""
    application_stems = _application_stems()
    if not application_stems:
        pytest.skip("No applications available in the filesystem or database")
    orphaned = _plan_stems() - application_stems
    assert orphaned == set(), (
        f"Plans with no matching application: {sorted(orphaned)}. "
        f"Move work-in-progress plans to {DRAFTS_DIR.relative_to(ROOT)}/ to exempt them."
    )


def test_draft_plans_are_exempt_from_the_orphan_check() -> None:
    """Guards the escape hatch itself: a draft must not be picked up by the orphan check."""
    assert not any(p.stem in _plan_stems() for p in DRAFTS_DIR.glob("*.json"))


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
