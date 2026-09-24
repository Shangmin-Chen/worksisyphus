"""Ingest subcommand handler: raw job fetching, scratch bridging, and ETL compilation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .....core.domain.ingestion import JobPosting, RawJobPayload
from ....outbound.ingestion.etl_compiler import EtlJobTransformer
from ....outbound.ingestion.http_fetcher import HttpRawFetcher
from ....outbound.ingestion.scratch_bridge import ScratchBridge
from ..helpers import InputReader


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "ingest",
        help="Ingest and compile job postings from URLs or files into structured JobPosting entities.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target posting URL, or action ('fetch' | 'compile').",
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="Posting URL (when target is 'fetch').",
    )
    parser.add_argument(
        "--file",
        "-f",
        default=None,
        help="Path to raw payload JSON or pre-cleaned JD text to compile.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path for fetched JD (defaults to .worksisyphus/scratch/current_jd.txt).",
    )
    parser.add_argument(
        "--company",
        default="",
        help="Override company name.",
    )
    parser.add_argument(
        "--role",
        default="",
        help="Override target role name.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON instead of human-readable summary.",
    )
    parser.set_defaults(handler=handle)


def _format_summary(posting: JobPosting, scratch_file: Path | None) -> str:
    word_count = len(posting.jd_text.split())
    scratch_desc = f" (saved to {scratch_file})" if scratch_file else ""
    lines = [
        f"Company:   {posting.company}",
        f"Role:      {posting.role}",
    ]
    if posting.location:
        lines.append(f"Location:  {posting.location}")
    lines.append(f"Source:    {posting.source_type} ({posting.url})")
    lines.append(f"JD Length: {word_count:,} words{scratch_desc}")

    if posting.screening_questions:
        lines.append(f"Questions: {len(posting.screening_questions)} screening questions extracted")
        for i, q in enumerate(posting.screening_questions, 1):
            req_str = "required" if q.required else "optional"
            lines.append(f'  {i}. [{q.question_type}] "{q.prompt}" ({req_str})')
            if q.options:
                opt_str = ", ".join(f"'{opt}'" for opt in q.options[:5])
                if len(q.options) > 5:
                    opt_str += f", ... (+{len(q.options) - 5} more)"
                lines.append(f"      Options: [{opt_str}]")
    return "\n".join(lines)


def _posting_to_dict(posting: JobPosting, scratch_file: Path | None) -> dict[str, object]:
    return {
        "company": posting.company,
        "role": posting.role,
        "location": posting.location,
        "url": posting.url,
        "source_type": posting.source_type,
        "jd_word_count": len(posting.jd_text.split()),
        "scratch_file": str(scratch_file) if scratch_file else None,
        "screening_questions": [
            {
                "id": q.question_id,
                "prompt": q.prompt,
                "type": q.question_type,
                "required": q.required,
                "options": list(q.options),
            }
            for q in posting.screening_questions
        ],
    }


def handle(args: argparse.Namespace, read_input: InputReader) -> int:
    bridge = ScratchBridge()
    fetcher = HttpRawFetcher()
    transformer = EtlJobTransformer()

    target = args.target

    if not target and not args.file:
        print(
            "error: Ingestion target required. Provide a URL, 'fetch <url>', or 'compile --file <path>'.",
            file=sys.stderr,
        )
        return 1

    # Action 1: `worksisyphus ingest fetch <url> [--output <file>]`
    if target == "fetch":
        url = args.url
        if not url:
            raise ValueError("URL required for 'ingest fetch <url>'.")
        payload = fetcher.fetch(url)
        # Determine cleaned JD text
        if payload.content_type == "application/json":
            posting = transformer.transform(payload, company_override=args.company, role_override=args.role)
            jd_text = posting.jd_text
        else:
            jd_text = transformer.transform(payload, company_override=args.company, role_override=args.role).jd_text

        out_path: Path
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(jd_text, encoding="utf-8")
        else:
            out_path = bridge.save_current_jd(jd_text)
            bridge.save_raw_payload(payload)

        word_count = len(jd_text.split())
        print(f"Fetched and pre-cleaned JD ({word_count:,} words) -> {out_path}")
        return 0

    # Action 2: `worksisyphus ingest compile --file <path> [--company <name>] [--role <role>]`
    if target == "compile" or args.file:
        file_path_str = args.file
        if not file_path_str and target == "compile":
            # Default to scratch file
            scratch_default = bridge.scratch_dir / "current_jd.txt"
            if scratch_default.is_file():
                file_path_str = str(scratch_default)
            else:
                raise FileNotFoundError(
                    f"No input file specified and default scratch file not found: {scratch_default}"
                )

        if not file_path_str:
            raise ValueError("Input file path required for compile.")

        file_path = Path(file_path_str)
        if not file_path.is_file():
            raise FileNotFoundError(f"Input file not found: {file_path}")

        file_content = file_path.read_text(encoding="utf-8").strip()

        # Check if file is a serialized RawJobPayload JSON, direct ATS JSON, or raw text
        if file_content.startswith("{"):
            try:
                data = json.loads(file_content)
                if isinstance(data, dict) and "raw_content" in data and "url" in data:
                    payload = RawJobPayload(
                        url=data.get("url", "file://" + str(file_path.resolve())),
                        raw_content=data.get("raw_content", ""),
                        content_type=data.get("content_type", "application/json"),
                        source_hint=data.get("source_hint", "generic"),
                        fetched_at=data.get("fetched_at", datetime.now(UTC).isoformat()),
                    )
                elif isinstance(data, dict):
                    # Direct ATS JSON response or structured posting JSON
                    source_hint = "generic"
                    if "questions" in data or "greenhouse" in file_path.name.lower():
                        source_hint = "greenhouse"
                    elif "categories" in data or "lever" in file_path.name.lower():
                        source_hint = "lever"
                    elif "descriptionHtml" in data or "ashby" in file_path.name.lower():
                        source_hint = "ashby"

                    payload = RawJobPayload(
                        url="file://" + str(file_path.resolve()),
                        raw_content=file_content,
                        content_type="application/json",
                        source_hint=source_hint,
                        fetched_at=datetime.now(UTC).isoformat(),
                    )
                else:
                    payload = RawJobPayload(
                        url="file://" + str(file_path.resolve()),
                        raw_content=file_content,
                        content_type="text/plain",
                        source_hint="generic",
                        fetched_at=datetime.now(UTC).isoformat(),
                    )
            except Exception:
                payload = RawJobPayload(
                    url="file://" + str(file_path.resolve()),
                    raw_content=file_content,
                    content_type="text/plain",
                    source_hint="generic",
                    fetched_at=datetime.now(UTC).isoformat(),
                )
        else:
            payload = RawJobPayload(
                url="file://" + str(file_path.resolve()),
                raw_content=file_content,
                content_type="text/plain",
                source_hint="generic",
                fetched_at=datetime.now(UTC).isoformat(),
            )

        posting = transformer.transform(payload, company_override=args.company, role_override=args.role)
        if args.json:
            print(json.dumps(_posting_to_dict(posting, file_path), indent=2))
        else:
            print(_format_summary(posting, file_path))
        return 0

    # Action 3: One-shot `worksisyphus ingest <url> [--json]`
    url = target
    payload = fetcher.fetch(url)
    posting = transformer.transform(payload, company_override=args.company, role_override=args.role)

    # Persist verbatim JD and raw payload to scratch
    scratch_file = bridge.save_current_jd(posting.jd_text)
    bridge.save_raw_payload(payload)

    if args.json:
        print(json.dumps(_posting_to_dict(posting, scratch_file), indent=2))
    else:
        print(_format_summary(posting, scratch_file))

    return 0
