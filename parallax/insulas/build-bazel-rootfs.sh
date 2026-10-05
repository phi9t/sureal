#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BAZEL_VERSION=9.2.0
BAZEL_LINUX_X86_64_SHA256=7668a95db1250f12c40407251e4e203b4ec8bf39bc495d2f485b2d8c99048694
CACHE_ROOT="${SURFLO_PATHWAY_BAZEL_ROOTFS_CACHE:-${HOME}/.cache/waystone/3d-pathway/insula}"
DEST="${SURFLO_PATHWAY_BAZEL_ROOTFS:-${CACHE_ROOT}/rootfs-v1}"
IMAGE_TAG="${SURFLO_PATHWAY_BAZEL_IMAGE_TAG:-sureal-3d-pathway-cpu:bazel-${BAZEL_VERSION}}"

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

rootfs_digest() {
    PYTHONPATH="${HERE}/../../autonomy" python3 - "$1" <<'PY'
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
        --setenv PATH /usr/local/bin:/usr/bin:/bin \
        --setenv PYTHONNOUSERSITE 1 \
        -- "$@"
}

validate_rootfs() {
    local rootfs="$1"
    local bazel_version
    local numpy_version
    local git_version

    command -v bwrap >/dev/null 2>&1 || die "bwrap is required to validate rootfs contents"
    bazel_version="$(run_in_rootfs "$rootfs" bazel --version)"
    [[ "$bazel_version" == "bazel ${BAZEL_VERSION}" ]] \
        || die "unexpected Bazel version in new rootfs: ${bazel_version}"
    numpy_version="$(run_in_rootfs "$rootfs" python -c 'import numpy; print(numpy.__version__)')"
    [[ "$numpy_version" == "1.26.4" ]] \
        || die "unexpected NumPy version in new rootfs: ${numpy_version}"
    git_version="$(run_in_rootfs "$rootfs" git --version)"
    [[ "$git_version" == git\ version\ * ]] \
        || die "git is unavailable in new rootfs: ${git_version}"
}

[[ ! -e "$DEST" ]] || die "refusing to replace existing rootfs: $DEST"
[[ ! -e "$DEST.lock.json" ]] || die "refusing to replace existing rootfs lock: $DEST.lock.json"
mkdir -p -- "$(dirname -- "$DEST")"
STAGE="$(mktemp -d "$(dirname -- "$DEST")/.rootfs.XXXXXX")"
STAGE_LOCK="$STAGE.lock.json"
CID=""
cleanup() {
    if [[ -n "$CID" ]]; then docker rm -f "$CID" >/dev/null; fi
    if [[ -n "${STAGE:-}" ]]; then rm -rf -- "$STAGE"; fi
    if [[ -n "${STAGE_LOCK:-}" ]]; then rm -f -- "$STAGE_LOCK"; fi
}
trap cleanup EXIT

docker build --platform linux/amd64 \
    --build-arg "BAZEL_VERSION=$BAZEL_VERSION" \
    --build-arg "BAZEL_LINUX_X86_64_SHA256=$BAZEL_LINUX_X86_64_SHA256" \
    -t "$IMAGE_TAG" -f "$HERE/bazel-rootfs.Dockerfile" "$HERE"
IMAGE="$(docker image inspect "$IMAGE_TAG" --format '{{.Id}}')"
CID="$(docker create "$IMAGE" /bin/true)"
docker export "$CID" | tar -C "$STAGE" -xf -
docker rm "$CID" >/dev/null
CID=""
validate_rootfs "$STAGE"
PYTHONPATH="${HERE}/../../autonomy" python3 - "$STAGE" "$HERE" "$IMAGE" "$BAZEL_VERSION" "$BAZEL_LINUX_X86_64_SHA256" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

from pipeline.runtime_identity import rootfs_identity

root, here, image, bazel_version, bazel_sha256 = (
    Path(sys.argv[1]),
    Path(sys.argv[2]),
    sys.argv[3],
    sys.argv[4],
    sys.argv[5],
)
lock = {
    "schema_version": 1,
    "platform": "linux/amd64",
    "image_id": image,
    "rootfs_sha256": rootfs_identity(root),
    "requirements_sha256": hashlib.sha256((here / "bazel-requirements.lock").read_bytes()).hexdigest(),
    "dockerfile_sha256": hashlib.sha256((here / "bazel-rootfs.Dockerfile").read_bytes()).hexdigest(),
    "bazel_version": bazel_version,
    "bazel_linux_x86_64_sha256": bazel_sha256,
    "python_version": "3.10",
    "numpy_version": "1.26.4",
    "required_tools": ["bazel", "git", "python"],
}
(root.parent / (root.name + ".lock.json")).write_text(json.dumps(lock, indent=2) + "\n")
PY
mv -- "$STAGE" "$DEST"
STAGE=""
mv -- "$STAGE_LOCK" "$DEST.lock.json"
STAGE_LOCK=""
printf 'rootfs=%s\nlock=%s\n' "$DEST" "$DEST.lock.json"
