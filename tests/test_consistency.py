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


def test_contact_verification_blocks_are_well_formed() -> None:
    """meta.json's contact_verification block, wherever present, is readable and complete.

    Application folders are immutable history, so the ~50 folders published before this field
    existed were deliberately NOT backfilled: nothing can reconstruct whether their contact was
    cross-checked, and inventing an answer would be exactly the silent-substitution mistake the
    field exists to prevent. Absent therefore means "not recorded" -- a third state, distinct
    from both verified and skipped. What is asserted here is that a block that IS present says
    something definite, and that a skip always carries its reason.
    """
    if not APPLICATIONS_DIR.is_dir() or not any(APPLICATIONS_DIR.iterdir()):
        pytest.skip("Applications directory not present or empty")
    invalid: list[str] = []
    for d in sorted(APPLICATIONS_DIR.iterdir()):
        meta_file = d / "meta.json"
        if not d.is_dir() or not meta_file.is_file():
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        verification = meta.get("contact_verification")
        if verification is None:  # published before the field existed; not backfillable
            continue
        if not isinstance(verification, dict):
            invalid.append(f"{d.name}: contact_verification is not an object")
            continue
        if not isinstance(verification.get("cross_checked_against_db"), bool):
            invalid.append(f"{d.name}: cross_checked_against_db is not a bool")
        elif not verification["cross_checked_against_db"] and not verification.get("skip_reason"):
            invalid.append(f"{d.name}: the cross-check was skipped without recording a reason")
    assert invalid == [], f"Malformed contact_verification blocks: {invalid}"
