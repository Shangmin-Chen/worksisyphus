"""ATS extraction check: verify a compiled resume PDF parses the way a recruiting system would.

Usage: uv run --with pdfminer.six python scripts/ats_check.py resumes/<name>.pdf

Checks that the text layer extracts cleanly: contact info findable, standard
section headers present, no broken glyphs, and (for tailored resumes) one page.
Exit 0 = pass, 1 = fail with one line per problem.
"""

from __future__ import annotations

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

    # Contact-field assertions are only meaningful against the profile the PDF was built from.
    # Without profile.json there is nothing authoritative to compare against, so skip those
    # checks loudly rather than silently passing empty strings and reporting a full pass.
    if profile_path.is_file():
        contact = load_profile(profile_path).contact
        name, email, phone = contact.name, contact.email, contact.phone
    else:
        print("NOTE: profile.json not found; skipping contact-field verification.")
        name = email = phone = ""

    result = check_pdf_ats(pdf_path=pdf, name=name, email=email, phone=phone)

    for warning in result.warnings:
        print(f"WARN: {warning}")

    if not result.passed:
        for problem in result.problems:
            print(f"FAIL: {problem}")
        return 1

    page_str = f"{result.pages} page{'s' if result.pages != 1 else ''}"
    print(f"ATS check passed: {pdf.name} ({page_str}, {result.word_count} words extracted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
