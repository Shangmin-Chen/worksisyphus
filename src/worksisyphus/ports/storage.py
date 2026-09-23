"""Storage Port: Abstract boundary protocol for persistence, audit tracking, and cloud sync."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..core.domain.models import Profile


@runtime_checkable
class StoragePort(Protocol):
    """Port interface for persisting resume data, application records, and audit events."""

    def save_application(
        self,
        app_id: str,
        company: str,
        role: str,
        date_str: str,
        source_url: str = "",
        status: str = "applied",
        jd_text: str = "",
        plan_json: str = "",
        evaluation_json: str | None = None,
    ) -> None:
        """Persist an application record atomically."""
        ...

    def list_applications(self) -> list[dict[str, str]]:
        """List all application records."""
        ...

    def update_application_status(self, app_id: str, new_status: str) -> None:
        """Update an application status."""
        ...

    def load_profile(self) -> Profile:
        """Load profile from storage."""
        ...

    def seed_database(self, profile: Profile) -> None:
        """Seed storage with a canonical profile."""
        ...

    def get_audit_history(self, limit: int = 50, entity_type: str | None = None) -> list[dict[str, Any]]:
        """Retrieve append-only audit trail records."""
        ...
