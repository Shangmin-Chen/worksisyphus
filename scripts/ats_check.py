"""ATS extraction check: verify a compiled resume PDF parses the way a recruiting system would.

Usage: uv run --with pdfminer.six python scripts/ats_check.py resumes/<name>.pdf

Checks that the text layer extracts cleanly: contact info findable, standard
section headers present, no broken glyphs, and (for tailored resumes) one page.
Exit 0 = pass, 1 = fail with one line per problem.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_STEM = "Simon_Chen_Resume_Compiled"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: ats_check.py <resume.pdf>", file=sys.stderr)
        return 1
    pdf = Path(sys.argv[1])
    contact = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))["contact"]
    text = extract_text(pdf)
    with pdf.open("rb") as fh:
        pages = sum(1 for _ in PDFPage.get_pages(fh))

    problems: list[str] = []
    if pdf.stem != CANONICAL_STEM and pages != 1:
        problems.append(f"expected 1 page, got {pages}")
    for label, needle in (("name", contact["name"]), ("email", contact["email"]), ("phone", contact["phone"])):
        if needle and needle not in text:
            problems.append(f"contact {label} {needle!r} did not extract")
    for section in ("Education", "Experience", "Technical Skills"):
        if section not in text:
            problems.append(f"section header {section!r} did not extract")
    if "(cid:" in text:
        problems.append("broken glyphs: extraction produced (cid:N) placeholders")
    merges = re.findall(r"[A-Za-z]{3,}(?:January|February|March|April|May|June|July|August|September|October|November|December) 20\d\d", text)
    for merge in merges:
        print(f"WARN: {merge!r} extracted with no whitespace before the date; that keyword will not match")

    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1
    print(f"ATS check passed: {pdf.name} ({pages} page{'s' if pages != 1 else ''}, {len(text.split())} words extracted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
