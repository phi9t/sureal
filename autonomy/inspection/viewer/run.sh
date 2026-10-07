#!/usr/bin/env bash
# Waymo Perception viewer dispatcher: exporter (Python) and web app (Vite).
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
VENV="${WAYMO_VIEWER_VENV:-$HERE/.venv}"
CACHE="${WAYMO_VIEWER_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/waystone/waymo-perception/viewer}"
PY="$VENV/bin/python"

usage() {
    cat <<'USAGE'
Usage: run.sh COMMAND [ARGS]

  setup                         create .venv with uv, install pinned deps, npm ci
  test                          run inspection/exporter tests through Bazel in Insula
  export SLICE CONTEXT [ARGS]   export one context into $WAYMO_VIEWER_CACHE/bundles
  verify SLICE CONTEXT [ARGS]   independently verify an exported bundle
  dev                           vite dev server serving bundles from the cache
  build                         production build into web/dist
  serve [PORT]                  serve web/dist plus bundles with the stdlib server
  pages OUT_DIR [IMG_DIR]       assemble the GitHub Pages site (landing + built viewer)

Environment: WAYMO_VIEWER_CACHE (default ~/.cache/waystone/waymo-perception/viewer),
WAYMO_VIEWER_VENV (default ./.venv).
USAGE
}

need_venv() { [[ -x "$PY" ]] || { echo "error: run '$0 setup' first ($PY missing)" >&2; exit 1; }; }
slice_id() { "$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["slice_id"])' "$1/slice.json"; }

cmd="${1:-}"
[[ -n "$cmd" ]] || { usage >&2; exit 2; }
shift
case "$cmd" in
    -h|--help|help) usage ;;
    setup)
        command -v uv >/dev/null || { echo "error: uv is required" >&2; exit 1; }
        uv venv "$VENV" --python 3.12
        uv pip install --python "$PY" -r "$HERE/export/requirements.lock"
        (cd "$HERE/web" && npm ci)
        ;;
    test)
        "$ROOT/../bazelw" test //autonomy/inspection:all_tests "$@"
        ;;
    export)
        need_venv
        [[ $# -ge 2 ]] || { usage >&2; exit 2; }
        slice="$1"; context="$2"; shift 2
        (cd "$ROOT" && "$PY" -m inspection.viewer.export.export --slice "$slice" --context "$context" --out "$CACHE" "$@")
        ;;
    verify)
        need_venv
        [[ $# -ge 2 ]] || { usage >&2; exit 2; }
        slice="$1"; context="$2"; shift 2
        bundle="$CACHE/bundles/$(slice_id "$slice")/$context"
        (cd "$ROOT" && "$PY" -m inspection.viewer.export.verify --slice "$slice" --context "$context" --bundle "$bundle" "$@")
        ;;
    dev)
        (cd "$HERE/web" && WAYMO_VIEWER_BUNDLES="$CACHE/bundles" npx vite "$@")
        ;;
    build)
        (cd "$HERE/web" && npx vite build "$@")
        ;;
    pages)
        [[ $# -ge 1 ]] || { usage >&2; exit 2; }
        out="$1"; img="${2:-}"
        (cd "$HERE/web" && npx vite build)
        rm -rf -- "$out"; mkdir -p -- "$out/viewer" "$out/img"
        cp -- "$HERE/site/index.html" "$out/"
        cp -R -- "$HERE/web/dist/." "$out/viewer/"
        touch -- "$out/.nojekyll"
        [[ -z "$img" ]] || cp -- "$img"/*.jpg "$out/img/"
        echo "pages site assembled at $out"
        ;;
    serve)
        need_venv
        (cd "$ROOT" && "$PY" -m inspection.viewer.export.serve --dist "$HERE/web/dist" --bundles "$CACHE/bundles" --port "${1:-8420}")
        ;;
    *) usage >&2; exit 2 ;;
esac
