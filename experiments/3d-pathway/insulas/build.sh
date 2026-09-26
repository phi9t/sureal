#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="${SURFLO_PATHWAY_CONTAINER_ENGINE:-docker}"

command -v "${ENGINE}" >/dev/null 2>&1 || {
    printf 'error: container engine not found: %s\n' "${ENGINE}" >&2
    exit 2
}

"${ENGINE}" build --network host --tag surflo-pathway-classical:1 "${HERE}/classical"
"${ENGINE}" build --network host --tag surflo-pathway-neural-rendering:1 "${HERE}/neural-rendering"
