#!/usr/bin/env bash
# Networked provisioning; offline execution uses enter.sh.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE="$(cd -- "${HERE}/.." && pwd)"
BAZEL_VERSION=9.2.0
BAZEL_LINUX_X86_64_SHA256=7668a95db1250f12c40407251e4e203b4ec8bf39bc495d2f485b2d8c99048694
CACHE_ROOT="${WAYMO_INSULA_CACHE_ROOT:-${HOME}/.cache/waystone/waymo-perception/insula}"
PREVIOUS="${WAYMO_INSULA_PREVIOUS_ROOT:-${CACHE_ROOT}/rootfs-v3}"
DEST="${WAYMO_INSULA_ROOT:-${CACHE_ROOT}/rootfs-v4}"
IMAGE_TAG="${WAYMO_INSULA_IMAGE_TAG:-sureal-waymo-cpu:bazel-${BAZEL_VERSION}-rootfs-v4}"

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

rootfs_digest() {
    PYTHONPATH="$PACKAGE" python3 - "$1" <<'PY'
import sys
from pathlib import Path
from insula.runtime_identity import rootfs_identity

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
    run_in_rootfs "$rootfs" sh -lc \
        "command -v git >/dev/null && command -v curl >/dev/null && command -v g++ >/dev/null && command -v ar >/dev/null && python -m pytest --version >/dev/null" \
        || die "new rootfs is missing required test tools"

    previous_packages="$(mktemp)"
    new_packages="$(mktemp)"
    run_in_rootfs "$previous" python -m pip freeze --all | LC_ALL=C sort >"$previous_packages"
    run_in_rootfs "$rootfs" python -m pip freeze --all | LC_ALL=C sort >"$new_packages"
    if ! python3 - "$previous_packages" "$new_packages" "$HERE/cpu-test-tools-requirements.lock" <<'PY'
import sys
from pathlib import Path

def canonical(name):
    return name.replace("_", "-").lower()

def inventory(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if "==" not in line or line.lstrip().startswith("#"):
            continue
        name, version = line.split("==", 1)
        result[canonical(name)] = version.split()[0].rstrip("\\")
    return result

previous = inventory(sys.argv[1])
new = inventory(sys.argv[2])
allowed = inventory(sys.argv[3])

errors = []
for name, version in sorted(previous.items()):
    if name not in new:
        errors.append(f"removed {name}=={version}")
    elif new[name] != version:
        errors.append(f"changed {name}: {version} -> {new[name]}")
for name, version in sorted(allowed.items()):
    if new.get(name) != version:
        errors.append(f"missing locked test tool {name}=={version}")
for name, version in sorted(new.items()):
    if name not in previous and name not in allowed:
        errors.append(f"unexpected new package {name}=={version}")
if errors:
    print("\\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
PY
    then
        diff -u "$previous_packages" "$new_packages" >&2 || true
        rm -f "$previous_packages" "$new_packages"
        die "Python package inventory differs between previous and new rootfs"
    fi
    rm -f "$previous_packages" "$new_packages"
}

[[ -d "$PREVIOUS" ]] || die "previous rootfs missing: $PREVIOUS"
[[ -f "$PREVIOUS.lock.json" ]] || die "previous rootfs lock missing: $PREVIOUS.lock.json"
[[ ! -e "$DEST" ]] || die "refusing to replace existing rootfs: $DEST"
[[ ! -e "$DEST.lock.json" ]] || die "refusing to replace existing rootfs lock: $DEST.lock.json"
mkdir -p -- "$(dirname -- "$DEST")"
STAGE="$(mktemp -d "$(dirname -- "$DEST")/.rootfs.XXXXXX")"
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
    -t "$IMAGE_TAG" -f "$HERE/Dockerfile" "$PACKAGE"
IMAGE="$(docker image inspect "$IMAGE_TAG" --format '{{.Id}}')"
CID="$(docker create "$IMAGE" /bin/true)"
docker export "$CID" | tar -C "$STAGE" -xf -
docker rm "$CID" >/dev/null
CID=""
validate_new_rootfs "$STAGE" "$PREVIOUS"
[[ "$(rootfs_digest "$PREVIOUS")" == "$PREVIOUS_IDENTITY" ]] \
    || die "previous rootfs identity changed during build"
[[ "$(sha256sum "$PREVIOUS.lock.json" | awk '{print $1}')" == "$PREVIOUS_LOCK_SHA256" ]] \
    || die "previous rootfs lock changed during build"
PYTHONPATH="$PACKAGE" python3 - "$STAGE" "$PACKAGE" "$HERE" "$IMAGE" "$BAZEL_VERSION" "$BAZEL_LINUX_X86_64_SHA256" <<'PY'
import json, sys
from pathlib import Path
from evidence.source_snapshot import file_sha256
from insula.runtime_identity import rootfs_identity
root, package, script_dir, image, bazel_version, bazel_sha256 = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6]
lock = {'schema_version': 1, 'platform': 'linux/amd64', 'image_id': image,
        'rootfs_sha256': rootfs_identity(root),
        'requirements_sha256': file_sha256(package/'requirements-tracer.lock'),
        'test_tools_requirements_sha256': file_sha256(script_dir/'cpu-test-tools-requirements.lock'),
        'dockerfile_sha256': file_sha256(script_dir/'Dockerfile'),
        'bazel_version': bazel_version,
        'bazel_linux_x86_64_sha256': bazel_sha256}
(root.parent/(root.name+'.lock.json')).write_text(json.dumps(lock, indent=2)+'\n')
PY
mv -- "$STAGE" "$DEST"
STAGE=""
mv -- "$STAGE_LOCK" "$DEST.lock.json"
STAGE_LOCK=""
printf 'rootfs=%s\nlock=%s\n' "$DEST" "$DEST.lock.json"
