"""FileSystem Rubrics Loader: Implements RoleRubricPort loading roles from roles/ directory."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ....core.domain.scoring import Category, Role, synthesize_role_rubric

ROLES_DIR = Path(__file__).resolve().parents[3] / "roles"
UPSTREAM_MANIFEST_PATH = ROLES_DIR / "upstream_manifest.json"


def list_roles(roles_dir: Path | None = None) -> list[str]:
    """List all available role rubric names."""
    active_dir = roles_dir or ROLES_DIR
    if not active_dir.is_dir():
        return []
    return sorted(d.name for d in active_dir.iterdir() if (d / "role.json").is_file())


def load_role(
    role_name: str = "startup_product_engineer",
    jd_text: str | None = None,
    roles_dir: Path | None = None,
) -> Role:
    """Load a role specification from the roles/ directory, or synthesize from JD if missing."""
    active_dir = roles_dir or ROLES_DIR
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", role_name.lower()).strip("_")
    role_dir = active_dir / slug
    if not role_dir.is_dir() or not (role_dir / "role.json").is_file():
        if jd_text and jd_text.strip():
            return synthesize_role_rubric(role_name=slug, jd_text=jd_text)
        available = list_roles(roles_dir=active_dir)
        raise FileNotFoundError(f"Role '{role_name}' not found. Available roles: {', '.join(available)}")

    manifest = json.loads((role_dir / "role.json").read_text(encoding="utf-8"))
    criteria_text = (role_dir / "criteria.jinja").read_text(encoding="utf-8")
    system_text = (role_dir / "system_message.jinja").read_text(encoding="utf-8")

    categories = [
        Category(key=c["key"], label=c["label"], max=c["max"], icon=c.get("icon", "•")) for c in manifest["categories"]
    ]

    return Role(
        name=slug,
        position_title=manifest.get("position_title", role_name),
        categories=categories,
        bonus_max=manifest.get("bonus_max", 10),
        min_final_score=manifest.get("min_final_score", 0),
        max_final_score=manifest.get("max_final_score", 110),
        criteria_template=criteria_text,
        system_message=system_text,
    )


class FileSystemRoleRubricAdapter:
    """RoleRubricPort implementation using roles/ directory files."""

    def load_role(self, role_name: str, jd_text: str | None = None) -> Role:
        return load_role(role_name=role_name, jd_text=jd_text)

    def list_roles(self) -> list[str]:
        return list_roles()
