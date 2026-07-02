from __future__ import annotations

import json
import unittest

from worksisyphus.enricher.extract import extract_jobright_detail


class EnricherTest(unittest.TestCase):
    def test_extracts_jobright_embedded_detail(self) -> None:
        job_posting = {
            "@type": "JobPosting",
            "title": "Software Engineer",
            "description": "<p>Build systems.</p><ul><li>Write Python</li></ul>",
            "employmentType": "FULL_TIME",
            "validThrough": "2026-07-01T00:00:00",
            "hiringOrganization": {
                "name": "ExampleCo",
                "sameAs": "https://example.com",
            },
        }
        helper = {
            "jobResult": {
                "jobId": "abc",
                "jobTitle": "Software Engineer",
                "jobNlpTitle": "Software Engineer",
                "jobSeniority": "Entry Level",
                "jobLocation": "New York, NY",
                "jobLocations": ["New York, NY"],
                "isRemote": False,
                "workModel": "Hybrid",
                "publishTime": "2026-06-25 12:00:00",
                "employmentType": "Full-time",
                "jobSummary": "Build systems.",
                "coreResponsibilities": ["Write Python"],
                "jdCoreSkills": [{"skill": "Python"}],
                "isDeleted": False,
                "isH1bSponsor": True,
                "isWorkAuthRequired": False,
                "isCitizenOnly": False,
                "isClearanceRequired": False,
                "qualifications": {
                    "mustHave": ["Python"],
                    "preferredHave": ["Postgres"],
                },
            },
            "companyResult": {
                "companyName": "ExampleCo",
                "companyURL": "https://example.com",
                "companySize": "1-10 employees",
            },
        }
        html = f"""
        <html><head>
        <script id="job-posting" type="application/ld+json">{json.dumps(job_posting)}</script>
        <script id="jobright-helper-job-detail-info" type="application/json">{json.dumps(helper)}</script>
        </head></html>
        """
        normalized = {
            "identity": {"canonical_id": "job_abc"},
            "company": {"name": "ExampleCo"},
        }

        extracted = extract_jobright_detail(
            html=html,
            source_url="https://jobright.ai/jobs/info/abc",
            normalized_job=normalized,
            fetched_at="2026-06-25T12:00:00+00:00",
        )

        self.assertEqual(extracted.status, "ok")
        self.assertEqual(extracted.record["company"]["name"], "ExampleCo")
        self.assertEqual(extracted.record["role"]["seniority"], "Entry Level")
        self.assertEqual(extracted.record["status"]["active_status"], "active")
        self.assertEqual(extracted.record["description"]["skills"], ["Python"])
        self.assertIn("Build systems.", extracted.record["description"]["text"])
        self.assertIn("Write Python", extracted.record["description"]["text"])


if __name__ == "__main__":
    unittest.main()
