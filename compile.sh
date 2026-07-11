#!/bin/sh
# Rebuild the canonical full resume.
set -eu
cd "$(dirname "$0")"
exec uv run python -m worksisyphus compile
