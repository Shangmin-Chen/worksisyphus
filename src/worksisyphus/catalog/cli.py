from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from worksisyphus.catalog.db import application_status, mark_applied

DEFAULT_DB_PATH = Path(".worksisyphus") / "catalog.sqlite3"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="worksisyphus-catalog",
        description="Inspect and update the persistent job catalog.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"catalog SQLite path; default: {DEFAULT_DB_PATH}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="show one job status")
    status_parser.add_argument("canonical_id")

    applied_parser = subparsers.add_parser(
        "mark-applied",
        help="mark a job as manually applied",
    )
    applied_parser.add_argument("canonical_id")
    applied_parser.add_argument("--notes", default=None)

    args = parser.parse_args(argv)
    db_path = args.db.expanduser().resolve()

    if args.command == "status":
        status = application_status(db_path, args.canonical_id)
        if status is None:
            print(f"{args.canonical_id}: not_found")
            return 1
        print(f"{args.canonical_id}: {status}")
        return 0

    if args.command == "mark-applied":
        applied_at = datetime.now(timezone.utc).isoformat()
        mark_applied(
            db_path,
            canonical_id=args.canonical_id,
            applied_at=applied_at,
            notes=args.notes,
        )
        print(f"{args.canonical_id}: applied at {applied_at}")
        return 0

    return 2
