"""Lint-style tests that verify plan/archive consistency across the repo."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLANS_DIR = ROOT / "plans"
APPLICATIONS_DIR = ROOT / "applications"


def _plan_slugs() -> set[str]:
    return {p.stem for p in PLANS_DIR.glob("*.json") if p.stem != "example"}


def _archive_slugs() -> set[str]:
    return {
        "_".join(d.name.split("_")[1:])
        for d in APPLICATIONS_DIR.iterdir()
        if d.is_dir()
    }


def test_every_plan_has_a_matching_archive() -> None:
    orphaned = _plan_slugs() - _archive_slugs()
    assert orphaned == set(), f"Plans without matching archives: {sorted(orphaned)}"


def test_every_archive_has_required_files() -> None:
    missing: list[str] = []
    for d in sorted(APPLICATIONS_DIR.iterdir()):
        if not d.is_dir():
            continue
        for name in ("jd.txt", "meta.json", "Simon_Chen_Resume.pdf"):
            if not (d / name).is_file():
                missing.append(f"{d.name}/{name}")
    assert missing == [], f"Missing archive files: {missing}"
