from __future__ import annotations

import unittest

from worksisyphus.aggregator.config import JOBRIGHT_2026_SE_NEW_GRAD
from worksisyphus.aggregator.jobright_parser import parse_jobright_readme


class JobrightParserTest(unittest.TestCase):
    def test_parses_table_rows_and_inherits_company_for_continuations(self) -> None:
        readme = """
# Jobs

| Company | Job Title | Location | Work Model | Date Posted |
| ----- | --------- |  --------- | ---- | ------- |
| **[OpenEye](http://openeye.net)** | **[Software QA Specialist](https://jobright.ai/jobs/info/abc123?utm_campaign=x)** | Liberty Lake, Washington | Hybrid | Jun 14 |
| \u21b3 | **[Software QA Specialist](https://jobright.ai/jobs/info/def456?utm_campaign=x)** | Liberty Lake, WA | On Site | Jun 14 |

Other text.
"""

        records = parse_jobright_readme(
            readme,
            source=JOBRIGHT_2026_SE_NEW_GRAD,
            commit_sha="a" * 40,
        )

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["extracted"]["company"], "OpenEye")
        self.assertEqual(records[0]["extracted"]["company_url"], "http://openeye.net")
        self.assertFalse(records[0]["extracted"]["is_company_continuation"])
        self.assertEqual(records[0]["extracted"]["jobright_id"], "abc123")
        self.assertEqual(records[1]["extracted"]["company"], "OpenEye")
        self.assertEqual(records[1]["extracted"]["company_url"], "http://openeye.net")
        self.assertTrue(records[1]["extracted"]["is_company_continuation"])
        self.assertEqual(records[1]["extracted"]["jobright_id"], "def456")

    def test_stops_after_daily_table(self) -> None:
        readme = """
| Company | Job Title | Location | Work Model | Date Posted |
| ----- | --------- |  --------- | ---- | ------- |
| **[One](https://one.example)** | **[Role](https://jobright.ai/jobs/info/one)** | Remote | Remote | Jun 14 |

| Company | Job Title | Location | Work Model | Date Posted |
| **[Two](https://two.example)** | **[Role](https://jobright.ai/jobs/info/two)** | Remote | Remote | Jun 13 |
"""

        records = parse_jobright_readme(
            readme,
            source=JOBRIGHT_2026_SE_NEW_GRAD,
            commit_sha="b" * 40,
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["extracted"]["company"], "One")

    def test_parses_links_with_brackets_in_link_text(self) -> None:
        readme = """
| Company | Job Title | Location | Work Model | Date Posted |
| ----- | --------- |  --------- | ---- | ------- |
| **[Cuckoo Rental America, Inc.](https://www.cuckooamerica.com/)** | **[[CKRA] IT Developer](https://jobright.ai/jobs/info/6a2a3440c07d4b6ae1c44fa3?utm_campaign=x)** | Los Angeles, CA | On Site | Jun 12 |
"""

        records = parse_jobright_readme(
            readme,
            source=JOBRIGHT_2026_SE_NEW_GRAD,
            commit_sha="c" * 40,
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["extracted"]["job_title"], "[CKRA] IT Developer")
        self.assertEqual(
            records[0]["extracted"]["job_url"],
            "https://jobright.ai/jobs/info/6a2a3440c07d4b6ae1c44fa3?utm_campaign=x",
        )
        self.assertEqual(
            records[0]["extracted"]["jobright_id"],
            "6a2a3440c07d4b6ae1c44fa3",
        )


if __name__ == "__main__":
    unittest.main()
