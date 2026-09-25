#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CACHE_ROOT="${PHOTOREAL_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/surflo/photoreal-scenes}"
ROOTFS="${PHOTOREAL_INSULA_ROOT:-${CACHE_ROOT}/rootfs}"
IMAGE="${PHOTOREAL_INSULA_IMAGE:-surflo-photoreal-blender:4.5.14}"

if command -v docker >/dev/null 2>&1; then
    CONTAINER_TOOL=docker
elif command -v podman >/dev/null 2>&1; then
    CONTAINER_TOOL=podman
else
    printf 'error: docker or podman is required\n' >&2
    exit 2
fi

"${CONTAINER_TOOL}" build \
    --file "${HERE}/insula/Dockerfile" \
    --tag "${IMAGE}" \
    "${HERE}/insula"
PHOTOREAL_CACHE_ROOT="${CACHE_ROOT}" PHOTOREAL_INSULA_ROOT="${ROOTFS}" \
    "${HERE}/insula/build_rootfs.sh" --dest "${ROOTFS}" --image "${IMAGE}"
