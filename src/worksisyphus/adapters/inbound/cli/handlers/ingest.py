"""Ingest subcommand handler: raw job fetching and pre-cleaning to scratch disk."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ....outbound.ingestion.http_fetcher import HttpRawFetcher
from ....outbound.ingestion.pre_cleaner import clean_html
from ....outbound.ingestion.scratch_bridge import ScratchBridge
from ..helpers import InputReader


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "ingest",
        help="Fetch a job posting URL, strip HTML noise, and write verbatim text to scratch.",
    )
    parser.add_argument(
        "url",
        help="Posting URL to ingest.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (defaults to .worksisyphus/scratch/current_jd.txt).",
    )
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace, read_input: InputReader) -> int:
    url = args.url
    if not url:
        print("error: URL is required for ingest.", file=sys.stderr)
        return 1

    fetcher = HttpRawFetcher()
    payload = fetcher.fetch(url)
    cleaned_jd = clean_html(payload.raw_content)

    if not cleaned_jd.strip():
        print(f"error: No readable content extracted from {url}", file=sys.stderr)
        return 1

    out_path: Path
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(cleaned_jd, encoding="utf-8")
    else:
        bridge = ScratchBridge()
        out_path = bridge.save_current_jd(cleaned_jd)

    word_count = len(cleaned_jd.split())
    print(f"Ingested:  {url}")
    print(f"Saved:     {out_path} ({word_count:,} words)")
    return 0
