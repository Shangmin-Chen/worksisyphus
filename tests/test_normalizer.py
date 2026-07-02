from __future__ import annotations

import unittest
from datetime import datetime, timezone

from worksisyphus.normalizer.normalize import normalize_payload, normalize_record
from worksisyphus.normalizer.schema import SCHEMA_VERSION


class NormalizerTest(unittest.TestCase):
    def test_normalizes_source_record_into_canonical_job(self) -> None:
        record = {
            "key": "source-key",
            "source": {
                "name": "jobright_ai_2026_software_engineer_new_grad",
                "repo": "https://github.com/jobright-ai/2026-Software-Engineer-New-Grad",
                "branch": "master",
                "path": "README.md",
                "commit": "a" * 40,
                "row_number": 60,
            },
            "extracted": {
                "company": "OpenEye",
                "company_url": "HTTP://OpenEye.NET",
                "job_title": "Software QA Specialist",
                "job_url": "https://jobright.ai/jobs/info/abc123?utm_campaign=x",
                "jobright_id": "abc123",
                "location": "Liberty Lake, Washington",
                "work_model": "On Site",
                "date_posted": "Jun 14",
            },
        }

        normalized = normalize_record(
            record,
            observed_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )

        self.assertEqual(normalized["schema_version"], SCHEMA_VERSION)
        self.assertEqual(
            normalized["identity"]["canonical_id"],
            "job_d42874e6e889f3a5df9001ab",
        )
        self.assertEqual(normalized["company"]["name"], "OpenEye")
        self.assertEqual(normalized["company"]["website_url"], "http://openeye.net")
        self.assertEqual(normalized["role"]["title"], "Software QA Specialist")
        self.assertEqual(normalized["workplace"]["type"], "onsite")
        self.assertEqual(normalized["posted"]["date"], "2026-06-14")
        self.assertEqual(normalized["locations"][0]["display"], "Liberty Lake, Washington")
        self.assertFalse(normalized["quality"]["needs_review"])

    def test_infers_previous_year_for_recent_rollover_dates(self) -> None:
        record = {
            "key": "source-key",
            "source": {"name": "jobright"},
            "extracted": {
                "company": "Example",
                "job_title": "Engineer",
                "job_url": "https://jobright.ai/jobs/info/rollover",
                "jobright_id": "rollover",
                "date_posted": "Dec 31",
            },
        }

        normalized = normalize_record(
            record,
            observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(normalized["posted"]["date"], "2025-12-31")

    def test_payload_normalization_sorts_by_canonical_id(self) -> None:
        payload = {
            "observed_at": "2026-06-15T06:33:09+00:00",
            "records": [
                {
                    "key": "two",
                    "source": {"name": "jobright"},
                    "extracted": {
                        "company": "Two",
                        "job_title": "Engineer",
                        "job_url": "https://jobright.ai/jobs/info/two",
                        "jobright_id": "two",
                    },
                },
                {
                    "key": "one",
                    "source": {"name": "jobright"},
                    "extracted": {
                        "company": "One",
                        "job_title": "Engineer",
                        "job_url": "https://jobright.ai/jobs/info/one",
                        "jobright_id": "one",
                    },
                },
            ],
        }

        normalized = normalize_payload(payload)

        self.assertEqual(
            [job["identity"]["source_job_id"] for job in normalized],
            ["one", "two"],
        )


if __name__ == "__main__":
    unittest.main()
