#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE="$(cd -- "$HERE/.." && pwd)"
DOCKERFILE="$HERE/Dockerfile.bazel-rootfs-v6"
BAZEL_VERSION=9.2.0
BAZEL_LINUX_X86_64_SHA256=7668a95db1250f12c40407251e4e203b4ec8bf39bc495d2f485b2d8c99048694
BASE_IMAGE_EXPECTED=sha256:eaf68603ced6f9abb5ee401522a07774183a8412ff3d9de61278f09c0738749d
CACHE_ROOT="${WAYMO_GPU_INSULA_CACHE_ROOT:-${HOME}/.cache/waystone/waymo-perception}"
PREVIOUS="${WAYMO_GPU_INSULA_PREVIOUS_ROOT:-${CACHE_ROOT}/gpu-rootfs}"
DEST="${WAYMO_GPU_INSULA_ROOT:-${CACHE_ROOT}/gpu-rootfs-v6}"
IMAGE_TAG="${WAYMO_GPU_INSULA_IMAGE_TAG:-sureal-waymo-gpu:bazel-${BAZEL_VERSION}-rootfs-v6}"

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

rootfs_digest() {
    PYTHONPATH="$PACKAGE" python3 - "$1" <<'PY'
import sys
from pathlib import Path
from pipeline.runtime_identity import rootfs_identity

print(rootfs_identity(Path(sys.argv[1])))
PY
}

run_in_rootfs() {
    local rootfs="$1"
    shift
    bwrap \
        --ro-bind "$rootfs" / \
        --proc /proc \
        --dev /dev \
        --tmpfs /tmp \
        --tmpfs /run \
        --dir /tmp/private-home \
        --unshare-all \
        --die-with-parent \
        --clearenv \
        --setenv HOME /tmp/private-home \
        --setenv PATH /opt/waymo/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin \
        --setenv PYTHONNOUSERSITE 1 \
        -- "$@"
}

validate_new_rootfs() {
    local rootfs="$1"
    local previous="$2"
    local bazel_version
    local previous_packages
    local new_packages

    command -v bwrap >/dev/null 2>&1 || die "bwrap is required to validate rootfs contents"
    bazel_version="$(run_in_rootfs "$rootfs" bazel --version)"
    [[ "$bazel_version" == "bazel ${BAZEL_VERSION}" ]] \
        || die "unexpected Bazel version in new rootfs: ${bazel_version}"

    previous_packages="$(mktemp)"
    new_packages="$(mktemp)"
    run_in_rootfs "$previous" uv pip freeze --python /opt/waymo/bin/python | LC_ALL=C sort >"$previous_packages"
    run_in_rootfs "$rootfs" uv pip freeze --python /opt/waymo/bin/python | LC_ALL=C sort >"$new_packages"
    if ! cmp -s "$previous_packages" "$new_packages"; then
        diff -u "$previous_packages" "$new_packages" >&2 || true
        rm -f "$previous_packages" "$new_packages"
        die "Python package inventory differs between previous and new rootfs"
    fi
    rm -f "$previous_packages" "$new_packages"
}

[[ -d "$PREVIOUS" ]] || die "previous GPU rootfs missing: $PREVIOUS"
[[ -f "$PREVIOUS.lock.json" ]] || die "previous GPU rootfs lock missing: $PREVIOUS.lock.json"
[[ ! -e "$DEST" ]] || die "refusing to replace existing rootfs: $DEST"
[[ ! -e "$DEST.lock.json" ]] || die "refusing to replace existing rootfs lock: $DEST.lock.json"

BASE_IMAGE_ACTUAL="$(docker image inspect surflo-insula:cuda13.2.1-locked --format '{{.Id}}')"
[[ "$BASE_IMAGE_ACTUAL" == "$BASE_IMAGE_EXPECTED" ]] \
    || die "GPU base image identity mismatch"

mkdir -p -- "$(dirname -- "$DEST")"
STAGE="$(mktemp -d "$(dirname -- "$DEST")/.gpu-rootfs.XXXXXX")"
STAGE_LOCK="$STAGE.lock.json"
CID=""
cleanup() {
    if [[ -n "$CID" ]]; then docker rm -f "$CID" >/dev/null; fi
    if [[ -n "$STAGE" ]]; then rm -rf -- "$STAGE"; fi
    if [[ -n "${STAGE_LOCK:-}" ]]; then rm -f -- "$STAGE_LOCK"; fi
}
trap cleanup EXIT

PREVIOUS_IDENTITY="$(rootfs_digest "$PREVIOUS")"
PREVIOUS_LOCK_SHA256="$(sha256sum "$PREVIOUS.lock.json" | awk '{print $1}')"

docker build --platform linux/amd64 \
    --build-arg "BAZEL_VERSION=$BAZEL_VERSION" \
    --build-arg "BAZEL_LINUX_X86_64_SHA256=$BAZEL_LINUX_X86_64_SHA256" \
    -t "$IMAGE_TAG" -f "$DOCKERFILE" "$HERE"
IMAGE="$(docker image inspect "$IMAGE_TAG" --format '{{.Id}}')"
CID="$(docker create "$IMAGE" /bin/true)"
docker export "$CID" | tar -C "$STAGE" -xf -
docker rm "$CID" >/dev/null
CID=""

validate_new_rootfs "$STAGE" "$PREVIOUS"
[[ "$(rootfs_digest "$PREVIOUS")" == "$PREVIOUS_IDENTITY" ]] \
    || die "previous GPU rootfs identity changed during build"
[[ "$(sha256sum "$PREVIOUS.lock.json" | awk '{print $1}')" == "$PREVIOUS_LOCK_SHA256" ]] \
    || die "previous GPU rootfs lock changed during build"

PYTHONPATH="$PACKAGE" python3 - "$STAGE" "$DOCKERFILE" "$HERE/requirements.lock" "$IMAGE" "$BAZEL_VERSION" "$BAZEL_LINUX_X86_64_SHA256" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

from pipeline.runtime_identity import rootfs_identity

root = Path(sys.argv[1])
dockerfile = Path(sys.argv[2])
requirements = Path(sys.argv[3])
image = sys.argv[4]
bazel_version = sys.argv[5]
bazel_sha256 = sys.argv[6]
lock = {
    "schema_version": 1,
    "platform": "linux/amd64",
    "image_id": image,
    "rootfs_sha256": rootfs_identity(root),
    "requirements_sha256": hashlib.sha256(requirements.read_bytes()).hexdigest(),
    "dockerfile_sha256": hashlib.sha256(dockerfile.read_bytes()).hexdigest(),
    "bazel_version": bazel_version,
    "bazel_linux_x86_64_sha256": bazel_sha256,
}
(root.parent / (root.name + ".lock.json")).write_text(json.dumps(lock, indent=2) + "\n")
PY

mv -- "$STAGE" "$DEST"
STAGE=""
mv -- "$STAGE_LOCK" "$DEST.lock.json"
STAGE_LOCK=""
printf 'rootfs=%s\nlock=%s\n' "$DEST" "$DEST.lock.json"
