from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from worksisyphus.catalog.db import (
    application_status,
    mark_applied,
    upsert_normalized_jobs,
)


class CatalogTest(unittest.TestCase):
    def test_upsert_preserves_applied_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "catalog.sqlite3"
            job = {
                "identity": {
                    "canonical_id": "job_123",
                    "dedupe_key": "dedupe_123",
                    "source_job_id": "source_123",
                    "source_record_key": "record_123",
                },
                "company": {"name": "Example"},
                "role": {"title": "Software Engineer"},
                "application": {
                    "source_listing_url": "https://jobright.ai/jobs/info/source_123"
                },
                "source": {"name": "jobright"},
            }
            first_seen = datetime(2026, 6, 25, tzinfo=timezone.utc).isoformat()

            upsert_normalized_jobs(
                db_path,
                jobs=[job],
                observed_at=first_seen,
                run_id="run1",
            )
            mark_applied(
                db_path,
                canonical_id="job_123",
                applied_at=first_seen,
                notes="Applied manually",
            )
            upsert_normalized_jobs(
                db_path,
                jobs=[job],
                observed_at=first_seen,
                run_id="run2",
            )

            self.assertEqual(application_status(db_path, "job_123"), "applied")


if __name__ == "__main__":
    unittest.main()
