#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE="${HERE}/pipeline"
exec python3 -c \
  'import runpy, sys; sys.path.insert(0, sys.argv[1]); script = sys.argv[2]; sys.argv = [script, *sys.argv[3:]]; runpy.run_path(script, run_name="__main__")' \
  "${PIPELINE}" \
  "${PIPELINE}/cli.py" \
  "$@"
