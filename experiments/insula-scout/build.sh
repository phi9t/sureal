#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CACHE_ROOT="${SURFLO_INSULA_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/surflo/insula-scout}"
SURFLO_INSULA_ROOT="${SURFLO_INSULA_ROOT:-${CACHE_ROOT}/rootfs}"
IMAGE="${SURFLO_INSULA_IMAGE:-surflo-insula:cuda13.2.1}"

if [[ -n "${SURFLO_INSULA_CONTAINER_ENGINE:-}" ]]; then
    CONTAINER_TOOL="${SURFLO_INSULA_CONTAINER_ENGINE}"
elif [[ -n "${SURFLO_PATHWAY_CONTAINER_ENGINE:-}" ]]; then
    CONTAINER_TOOL="${SURFLO_PATHWAY_CONTAINER_ENGINE}"
elif command -v docker >/dev/null 2>&1; then
    CONTAINER_TOOL=docker
elif command -v podman >/dev/null 2>&1; then
    CONTAINER_TOOL=podman
else
    echo "docker or podman is required" >&2
    exit 2
fi

command -v "${CONTAINER_TOOL}" >/dev/null 2>&1 || {
    echo "container engine not found: ${CONTAINER_TOOL}" >&2
    exit 2
}

"${CONTAINER_TOOL}" build \
    --file "${HERE}/insula/Dockerfile" \
    --tag "${IMAGE}" \
    "${HERE}/insula"

SURFLO_INSULA_CACHE_ROOT="${CACHE_ROOT}" \
    "${HERE}/insula/build_rootfs.sh" \
    --dest "${SURFLO_INSULA_ROOT}" \
    --image "${IMAGE}"

"${HERE}/enter.sh" /workspace/surflo/experiments/insula-scout/install_env.sh
