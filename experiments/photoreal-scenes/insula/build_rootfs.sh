#!/usr/bin/env bash
set -euo pipefail

CACHE_ROOT="${PHOTOREAL_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/surflo/photoreal-scenes}"
DEST="${PHOTOREAL_INSULA_ROOT:-${CACHE_ROOT}/rootfs}"
IMAGE="${PHOTOREAL_INSULA_IMAGE:-surflo-photoreal-blender:4.5.14}"
VALIDATE_ROOTFS=""
BLENDER_VERSION=4.5.14
BLENDER_SHA256=9ba871ff2ecd36526b77432745980b7e6664ecd0c7ca11c48849073dcfe06da3

usage() {
    cat <<'EOF'
Usage: build_rootfs.sh [--dest DIR] [--image IMAGE]
       build_rootfs.sh --validate-rootfs DIR

Export the pinned Blender OCI image into an atomically replaced rootfs.
EOF
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dest) DEST="${2:?--dest requires a value}"; shift 2 ;;
        --dest=*) DEST="${1#*=}"; shift ;;
        --image) IMAGE="${2:?--image requires a value}"; shift 2 ;;
        --image=*) IMAGE="${1#*=}"; shift ;;
        --validate-rootfs) VALIDATE_ROOTFS="${2:?--validate-rootfs requires a value}"; shift 2 ;;
        --validate-rootfs=*) VALIDATE_ROOTFS="${1#*=}"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown argument: $1" ;;
    esac
done

validate_rootfs() {
    local rootfs="$1"
    local contract="${rootfs}/etc/photoreal-blender-insula-contract"
    [[ -x "${rootfs}/bin/bash" ]] || die "exported image has no /bin/bash"
    [[ -x "${rootfs}/opt/blender/blender" ]] || die "exported image has no Blender executable"
    for mountpoint in workspace/surflo cache/blender exchange run/photoreal-nvidia-driver; do
        [[ -d "${rootfs}/${mountpoint}" ]] \
            || die "exported image has no /${mountpoint} mountpoint"
    done
    [[ -f "${contract}" ]] || die "Blender Insula contract is missing"
    [[ "$(sed -n 's/^schema_version=//p' "${contract}")" == 1 ]] \
        || die "unexpected Blender Insula schema"
    [[ "$(sed -n 's/^blender_version=//p' "${contract}")" == "${BLENDER_VERSION}" ]] \
        || die "unexpected Blender version in Insula contract"
    [[ "$(sed -n 's/^blender_archive_sha256=//p' "${contract}")" == "${BLENDER_SHA256}" ]] \
        || die "unexpected Blender archive hash in Insula contract"
}

if [[ -n "${VALIDATE_ROOTFS}" ]]; then
    validate_rootfs "${VALIDATE_ROOTFS}"
    printf 'rootfs=%s\n' "${VALIDATE_ROOTFS}"
    exit 0
fi

case "${DEST}" in
    ""|/|/bin|/boot|/dev|/etc|/home|/opt|/root|/run|/srv|/tmp|/usr|/var|"${HOME}")
        die "refusing unsafe rootfs destination: ${DEST}"
        ;;
esac

if command -v docker >/dev/null 2>&1; then
    CONTAINER_TOOL=docker
elif command -v podman >/dev/null 2>&1; then
    CONTAINER_TOOL=podman
else
    die "docker or podman is required"
fi
"${CONTAINER_TOOL}" image inspect "${IMAGE}" >/dev/null 2>&1 \
    || die "container image not found: ${IMAGE}"

mkdir -p "$(dirname -- "${DEST}")"
LOCK="${DEST}.lock"
if ! mkdir "${LOCK}" 2>/dev/null; then
    die "rootfs build lock is held: ${LOCK}"
fi
TMP="$(mktemp -d "$(dirname -- "${DEST}")/.blender-rootfs.XXXXXX")"
CID=""
BACKUP=""
cleanup() {
    [[ -z "${CID}" ]] || "${CONTAINER_TOOL}" rm -f "${CID}" >/dev/null 2>&1 || true
    [[ ! -d "${TMP}" ]] || rm -rf -- "${TMP}"
    rmdir "${LOCK}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

CID="$("${CONTAINER_TOOL}" create "${IMAGE}" /bin/true)"
"${CONTAINER_TOOL}" export "${CID}" | tar -C "${TMP}" -xf -
"${CONTAINER_TOOL}" rm -f "${CID}" >/dev/null
CID=""
validate_rootfs "${TMP}"

if [[ -e "${DEST}" ]]; then
    BACKUP="${DEST}.old.$$"
    mv -- "${DEST}" "${BACKUP}"
fi
mv -- "${TMP}" "${DEST}"
TMP=""
[[ -z "${BACKUP}" || ! -e "${BACKUP}" ]] || rm -rf -- "${BACKUP}"
printf 'rootfs=%s\n' "${DEST}"
