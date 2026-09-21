"""Backward-compatibility facade for CLI commands."""

from __future__ import annotations

import sys

from .adapters.inbound.cli import commands as _module
from .adapters.inbound.cli.commands import _latest_application_pdf, main

sys.modules[__name__] = _module

if __name__ == "__main__":
    main()

__all__ = ["_latest_application_pdf", "main"]
