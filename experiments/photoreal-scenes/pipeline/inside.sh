#!/usr/bin/env bash
set -euo pipefail

[[ "${PHOTOREAL_IN_INSULA:-0}" == 1 ]] || {
    printf 'error: pipeline workloads must run inside the Blender Insula\n' >&2
    exit 2
}

ROOT=/workspace/surflo/experiments/photoreal-scenes
ASSET_ROOT="${PHOTOREAL_ASSET_ROOT:-/cache/blender/assets}"
RUN_ROOT="${PHOTOREAL_RUN_ROOT:-/cache/blender/runs}"
command_name="${1:-}"
shift || true

case "${command_name}" in
    fetch)
        exec python3 "${ROOT}/pipeline/assets.py" fetch \
            --lock "${ROOT}/assets.lock.json" --asset-root "${ASSET_ROOT}"
        ;;
    verify-assets)
        exec python3 "${ROOT}/pipeline/assets.py" verify \
            --lock "${ROOT}/assets.lock.json" --asset-root "${ASSET_ROOT}"
        ;;
    render-draft|render|validate|contact-sheets|test)
        exec python3 "${ROOT}/pipeline/driver.py" "${command_name}" \
            --asset-root "${ASSET_ROOT}" --run-root "${RUN_ROOT}" "$@"
        ;;
    publish)
        exec python3 "${ROOT}/pipeline/exchange.py" \
            --run-root "${RUN_ROOT}" --exchange-root "${PHOTOREAL_EXCHANGE_ROOT:-/exchange}" "$@"
        ;;
    *)
        printf 'error: unknown in-Insula command: %s\n' "${command_name}" >&2
        exit 2
        ;;
esac
