#!/bin/sh
# Rebuild the canonical full resume (no AI).
set -eu
cd "$(dirname "$0")"
exec uv run python -m worksisyphus compile
