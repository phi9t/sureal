#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE="${HERE}/pipeline"
export PYTHONPATH="${PIPELINE}${PYTHONPATH:+:${PYTHONPATH}}"
exec python3 "${PIPELINE}/cli.py" "$@"
