#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${HERE}/../.." && pwd)"
CACHE_ROOT="${SURFLO_INSULA_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/surflo/insula-scout}"
SURFLO_INSULA_ROOT="${SURFLO_INSULA_ROOT:-${CACHE_ROOT}/rootfs}"
IMAGE="${SURFLO_INSULA_IMAGE:-surflo-insula:cuda13.2.1}"

if [[ "${1:-}" == "--emit-plan" ]]; then
    [[ $# -eq 1 ]] || { echo "--emit-plan takes no additional arguments" >&2; exit 2; }
    exec python3 "${HERE}/verify_environment_lock.py" --emit-plan
elif [[ $# -ne 0 ]]; then
    echo "unknown argument: $1" >&2
    exit 2
fi

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

python3 "${HERE}/verify_environment_lock.py" --emit-plan >/dev/null
git -C "${REPO_ROOT}" submodule update --init --recursive -- submodules/Depth-Anything-3
git -C "${REPO_ROOT}" submodule update --init --recursive -- submodules/nvdiffrast

readarray -t LOCK_VALUES < <(
    python3 - "${HERE}/foundation-environment.lock.json" <<'PY'
import json
import sys
from pathlib import Path

lock = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(lock["cuda_base_image"])
print(lock["ubuntu_snapshot"])
print(" ".join(lock["apt_packages"]))
print(lock["uv"]["version"])
print(lock["uv"]["sha256"])
PY
)
CUDA_BASE="${LOCK_VALUES[0]}"
UBUNTU_SNAPSHOT="${LOCK_VALUES[1]}"
APT_PACKAGES="${LOCK_VALUES[2]}"
UV_VERSION="${LOCK_VALUES[3]}"
UV_SHA256="${LOCK_VALUES[4]}"

"${CONTAINER_TOOL}" build \
    --file "${HERE}/insula/Dockerfile" \
    --tag "${IMAGE}" \
    --build-arg "CUDA_BASE=${CUDA_BASE}" \
    --build-arg "UBUNTU_SNAPSHOT=${UBUNTU_SNAPSHOT}" \
    --build-arg "APT_PACKAGES=${APT_PACKAGES}" \
    --build-arg "UV_VERSION=${UV_VERSION}" \
    --build-arg "UV_SHA256=${UV_SHA256}" \
    "${HERE}"

SURFLO_INSULA_CACHE_ROOT="${CACHE_ROOT}" \
    "${HERE}/insula/build_rootfs.sh" \
    --dest "${SURFLO_INSULA_ROOT}" \
    --image "${IMAGE}"

"${HERE}/enter.sh" /workspace/surflo/experiments/insula-scout/install_env.sh
