"""Lint-style tests that verify application and DB consistency across the repo."""

from __future__ import annotations

import json
from pathlib import Path

from worksisyphus.application import STATUSES

ROOT = Path(__file__).resolve().parents[1]
APPLICATIONS_DIR = ROOT / "applications"
FIXTURES_APPLICATIONS_DIR = ROOT / "tests" / "fixtures" / "applications"
FIXTURES_PROFILE_PATH = ROOT / "tests" / "fixtures" / "profile.json"


def get_all_application_dirs() -> list[Path]:
    """Return all application folders (committed fixtures + live folders if present).

    Must never be empty: the repo commits at least one fixture application folder in
    tests/fixtures/applications/ so that CI produces real assertions and never skips.
    """
    dirs: list[Path] = []
    if FIXTURES_APPLICATIONS_DIR.is_dir():
        dirs.extend([d for d in FIXTURES_APPLICATIONS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")])
    if APPLICATIONS_DIR.is_dir():
        dirs.extend([d for d in APPLICATIONS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")])
    assert dirs, (
        f"No application folders found in {FIXTURES_APPLICATIONS_DIR} or {APPLICATIONS_DIR}. "
        "Consistency tests fail closed when no application folders exist."
    )
    return dirs


def test_every_application_has_required_files() -> None:
    app_dirs = get_all_application_dirs()
    missing: list[str] = []
    for d in sorted(app_dirs):
        for name in ("jd.txt", "meta.json", "Simon_Chen_Resume.pdf"):
            if not (d / name).is_file():
                missing.append(f"{d.name}/{name}")
    assert missing == [], f"Missing application files: {missing}"


def test_every_application_meta_json_is_valid() -> None:
    app_dirs = get_all_application_dirs()
    invalid: list[str] = []
    for d in sorted(app_dirs):
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


def test_contact_verification_blocks_are_well_formed() -> None:
    """meta.json's contact_verification block, wherever present, is readable and complete.

    Application folders are immutable history, so the ~50 folders published before this field
    existed were deliberately NOT backfilled: nothing can reconstruct whether their contact was
    cross-checked, and inventing an answer would be exactly the silent-substitution mistake the
    field exists to prevent. Absent therefore means "not recorded" -- a third state, distinct
    from both verified and skipped. What is asserted here is that a block that IS present says
    something definite, and that a skip always carries its reason.
    """
    app_dirs = get_all_application_dirs()
    invalid: list[str] = []
    for d in sorted(app_dirs):
        meta_file = d / "meta.json"
        if not meta_file.is_file():
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


def test_trimmed_blocks_are_well_formed() -> None:
    """meta.json's trimmed list, wherever present, is readable and complete.

    Application folders are immutable history, so folders published before this field
    existed were deliberately NOT backfilled: nothing can reconstruct what the trim loop
    dropped, and inventing an answer would be dishonest. Absent therefore means "not
    recorded". What is asserted here is that a list that IS present names each cut with
    kind and slug, and bullet trims also carry the removed bullet slug.
    """
    app_dirs = get_all_application_dirs()
    invalid: list[str] = []
    for d in sorted(app_dirs):
        meta_file = d / "meta.json"
        if not meta_file.is_file():
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        trimmed = meta.get("trimmed")
        if trimmed is None:
            continue
        if not isinstance(trimmed, list):
            invalid.append(f"{d.name}: trimmed is not a list")
            continue
        for index, cut in enumerate(trimmed):
            if not isinstance(cut, dict):
                invalid.append(f"{d.name}: trimmed[{index}] is not an object")
                continue
            if cut.get("kind") not in ("project", "experience-bullet", "project-bullet"):
                invalid.append(f"{d.name}: trimmed[{index}] has invalid kind {cut.get('kind')!r}")
            elif not isinstance(cut.get("slug"), str) or not cut["slug"]:
                invalid.append(f"{d.name}: trimmed[{index}] missing slug")
            elif cut["kind"] != "project" and not cut.get("bullet"):
                invalid.append(f"{d.name}: trimmed[{index}] missing bullet")
    assert invalid == [], f"Malformed trimmed blocks: {invalid}"
