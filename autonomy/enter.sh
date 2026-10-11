#!/usr/bin/env bash
# Enters Sureal's pinned Insula runtime for repository commands.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$HERE"
exec python3 -m insula.entry "$@"
