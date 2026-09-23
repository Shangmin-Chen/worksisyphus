"""Status and update-status subcommand handlers."""

from __future__ import annotations

import argparse

from .....core.use_cases.application import (
    STATUSES,
    slugify,
)
from .. import commands
from ..helpers import InputReader, fit_column


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    # 1. status
    status_cmd = subparsers.add_parser("status", help="List all applications and their current statuses.")
    status_cmd.add_argument(
        "--company",
        default=None,
        help="Case-insensitive substring filter on the company name.",
    )
    status_cmd.set_defaults(handler=handle_status)

    # 2. update-status
    update_cmd = subparsers.add_parser("update-status", help="Update the status of an application.")
    update_cmd.add_argument(
        "--app",
        required=True,
        help="Full application folder name or unique stem; ambiguous stems are rejected with the list of matches.",
    )
    update_cmd.add_argument("--status", required=True, choices=STATUSES, help="New status value.")
    # Legacy flags accepted as no-ops
    update_cmd.add_argument("--no-sync", action="store_true", help=argparse.SUPPRESS)
    update_cmd.add_argument("--allow-branch", action="store_true", help=argparse.SUPPRESS)
    update_cmd.add_argument("--no-git-check", action="store_true", help=argparse.SUPPRESS)
    update_cmd.set_defaults(handler=handle_update_status)


def handle_status(args: argparse.Namespace, read_input: InputReader) -> int:
    apps = commands.list_applications()
    if args.company:
        needle = args.company.lower()
        apps = [app for app in apps if needle in app.get("company", "").lower()]
    if not apps:
        print("No applications found.")
        return 0

    attempts: dict[str, int] = {}
    for app in reversed(apps):
        key = slugify(app.get("company", ""))
        attempts[key] = attempts.get(key, 0) + 1
        app["attempt"] = str(attempts[key])

    header = f"{'Date':<12} {'Company':<20} {'Role':<32} {'Status':<15} {'App#':<5} Application"
    print(header)
    print("-" * len(header))
    for app in apps:
        key = slugify(app.get("company", ""))
        attempt_cell = f"#{app['attempt']}" if attempts[key] > 1 else ""
        print(
            f"{fit_column(app.get('date', ''), 12):<12} "
            f"{fit_column(app.get('company', ''), 20):<20} "
            f"{fit_column(app.get('role', ''), 32):<32} "
            f"{fit_column(app.get('status', ''), 15):<15} "
            f"{attempt_cell:<5} {app.get('folder', '')}"
        )
    return 0


def handle_update_status(args: argparse.Namespace, read_input: InputReader) -> int:
    folder, old_status, new_status = commands.update_application_status(
        args.app,
        args.status,
    )
    print(f"Updated {folder.name}: {old_status} -> {new_status}")
    return 0
