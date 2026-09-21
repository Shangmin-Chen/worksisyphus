"""Rubrics Port: Abstract boundary protocol for role rubrics discovery and loading."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..core.domain.scoring import Role


@runtime_checkable
class RoleRubricPort(Protocol):
    """Port interface for loading and listing role scoring rubrics."""

    def load_role(self, role_name: str, jd_text: str | None = None) -> Role:
        """Load role specification from store or dynamically synthesize from JD."""
        ...

    def list_roles(self) -> list[str]:
        """List all available role rubric names."""
        ...
