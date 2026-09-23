"""Database management subcommand handlers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..... import db as db_module
from ..helpers import InputReader


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    db_cmd = subparsers.add_parser("db", help="Manage local SQLite database layer.")
    db_sub = db_cmd.add_subparsers(dest="db_action", required=True)

    # 1. init
    init_cmd = db_sub.add_parser("init", help="Initialize and seed database from profile.json and applications/.")
    init_cmd.add_argument("--allow-branch", action="store_true", help=argparse.SUPPRESS)
    init_cmd.add_argument("--no-git-check", action="store_true", help=argparse.SUPPRESS)

    # 2. sync
    sync_cmd = db_sub.add_parser("sync", help="Sync database: load profile.json and applications into SQLite.")
    sync_cmd.add_argument("--allow-branch", action="store_true", help=argparse.SUPPRESS)
    sync_cmd.add_argument("--no-git-check", action="store_true", help=argparse.SUPPRESS)

    # 3. status
    db_sub.add_parser("status", help="Show database metrics and connection status.")

    # 4. export-profile
    export_cmd = db_sub.add_parser(
        "export-profile",
        help="Rebuild profile.json from the database. Recovery path when the gitignored profile is lost.",
    )
    export_cmd.add_argument("--output", default="profile.json", help="Destination path (default: profile.json).")
    export_cmd.add_argument(
        "--force",
        action="store_true",
        help=(
            "Overwrite the destination if it already exists. Does not bypass the placeholder "
            "check: a database holding scrubbed contact details is never exported."
        ),
    )

    # 5. history
    history_cmd = db_sub.add_parser("history", help="Show append-only audit trail.")
    history_cmd.add_argument("--limit", type=int, default=20, help="Number of audit events to display.")
    history_cmd.add_argument("--type", dest="entity_type", default=None, help="Filter by entity type.")

    db_cmd.set_defaults(handler=handle)


def handle(args: argparse.Namespace, read_input: InputReader) -> int:
    conn = db_module.get_connection(db_module.DEFAULT_DB_PATH)
    try:
        if args.db_action == "init":
            db_module.seed_database(conn)
            print(f"Initialized and seeded {db_module.DEFAULT_DB_PATH}")
            return 0
        elif args.db_action == "sync":
            db_module.seed_database(conn)
            print("Synced profile.json to SQLite")
            return 0
        elif args.db_action == "export-profile":
            destination = Path(args.output)
            if destination.exists() and not args.force:
                print(f"error: {destination} already exists; pass --force to overwrite.", file=sys.stderr)
                return 1
            db_module.export_profile_json(conn, destination)
            contact = db_module.load_profile_from_db(conn).contact
            print(f"Wrote {destination} from {db_module.DEFAULT_DB_PATH} ({contact.name} <{contact.email}>)")
            return 0
        elif args.db_action == "status":
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contact'")
            if not cur.fetchone():
                print("Database not initialized. Run 'worksisyphus db init' first.")
                return 0
            profile = db_module.load_profile_from_db(conn)
            events = db_module.get_audit_history(conn, limit=1)
            cur = conn.execute("SELECT count(*) FROM applications")
            app_count = cur.fetchone()[0]
            print(f"Database:     {db_module.DEFAULT_DB_PATH} (connected)")
            print(f"Contact:      {profile.contact.name} <{profile.contact.email}>")
            print(f"Experiences:  {len(profile.experiences)}")
            print(f"Projects:     {len(profile.projects)}")
            print(
                f"Skills:       {sum(len(v) for v in profile.skills.values())} across {len(profile.skills)} categories"
            )
            print(f"Applications: {app_count}")
            if events:
                print(f"Last change:  {events[0]['timestamp']} ({events[0]['action']} {events[0]['entity_type']})")
            return 0
        elif args.db_action == "history":
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_events'")
            if not cur.fetchone():
                print("Database not initialized. Run 'worksisyphus db init' first.")
                return 0
            events = db_module.get_audit_history(conn, limit=args.limit, entity_type=args.entity_type)
            if not events:
                print("No audit events found.")
                return 0
            header = f"{'Timestamp':<25} {'Action':<15} {'Entity':<18} {'Slug/ID':<30} Details"
            print(header)
            print("-" * 100)
            for ev in events:
                details = ""
                if ev.get("field_name"):
                    details = f"{ev['field_name']}: {ev.get('old_value', '')} -> {ev.get('new_value', '')}"
                elif ev.get("metadata"):
                    details = str(ev["metadata"])
                print(
                    f"{ev.get('timestamp', ''):<25} "
                    f"{ev.get('action', ''):<15} "
                    f"{ev.get('entity_type', ''):<18} "
                    f"{(ev.get('entity_slug') or ev.get('entity_id') or ''):<30} "
                    f"{details}"
                )
            return 0
        return 0
    finally:
        conn.close()
