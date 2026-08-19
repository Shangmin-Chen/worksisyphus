"""ATS extraction check: verify a compiled resume PDF parses the way a recruiting system would.

Usage: uv run --with pdfminer.six python scripts/ats_check.py resumes/<name>.pdf

Checks that the text layer extracts cleanly: contact info findable, standard
section headers present, no broken glyphs, and (for tailored resumes) one page.
Exit 0 = pass, 1 = fail with one line per problem.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus.ats import check_pdf_ats  # noqa: E402
from worksisyphus.profile import load_profile  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: ats_check.py <resume.pdf>", file=sys.stderr)
        return 1
    pdf = Path(sys.argv[1])
    profile_path = ROOT / "profile.json"
    if not profile_path.is_file():
        profile_path = ROOT / "profile.example.json"
    if not profile_path.is_file():
        profile_path = ROOT / "tests" / "fixtures" / "profile.json"

    profile = load_profile(profile_path)
    contact = profile.contact

    result = check_pdf_ats(
        pdf_path=pdf,
        name=contact.name,
        email=contact.email,
        phone=contact.phone,
    )

    merges = re.findall(
        r"[A-Za-z]{3,}(?:January|February|March|April|May|June|July|August|September|October|November|December) 20\d\d",
        result.text,
    )
    for merge in merges:
        print(f"WARN: {merge!r} extracted with no whitespace before the date; that keyword will not match")

    if not result.passed:
        for problem in result.problems:
            print(f"FAIL: {problem}")
        return 1

    page_str = f"{result.pages} page{'s' if result.pages != 1 else ''}"
    print(f"ATS check passed: {pdf.name} ({page_str}, {result.word_count} words extracted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
