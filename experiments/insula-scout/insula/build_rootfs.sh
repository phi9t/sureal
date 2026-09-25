#!/usr/bin/env bash
set -euo pipefail

CACHE_ROOT="${SURFLO_INSULA_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/surflo/insula-scout}"
DEST="${SURFLO_INSULA_ROOT:-${CACHE_ROOT}/rootfs}"
IMAGE="${SURFLO_INSULA_IMAGE:-surflo-insula:cuda13.2.1}"
VALIDATE_ROOTFS=""

usage() {
    cat <<'EOF'
Usage: build_rootfs.sh [--dest DIR] [--image IMAGE]
       build_rootfs.sh --validate-rootfs DIR

Export a locally built Surflo Insula OCI image into an atomic rootfs directory.

Options:
  --dest DIR      Rootfs destination (default: $SURFLO_INSULA_ROOT or cache/rootfs)
  --image IMAGE   Local Docker/Podman image to export
  --validate-rootfs DIR
                  Validate an existing exported rootfs and exit
  -h, --help      Show this help
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

rootfs_executable_exists() {
    local rootfs="$1"
    local path="$2"
    local pending resolved component candidate target
    local depth=0

    pending="${path#/}"
    resolved=""
    while [[ -n "${pending}" ]]; do
        ((depth += 1))
        ((depth <= 64)) || return 1
        component="${pending%%/*}"
        if [[ "${pending}" == */* ]]; then
            pending="${pending#*/}"
        else
            pending=""
        fi
        case "${component}" in
            ""|.) continue ;;
            ..) resolved="${resolved%/*}"; continue ;;
        esac
        candidate="${rootfs}/${resolved:+${resolved}/}${component}"
        if [[ -L "${candidate}" ]]; then
            target="$(readlink -- "${candidate}")"
            if [[ "${target}" == /* ]]; then
                resolved=""
                target="${target#/}"
            fi
            pending="${target}${pending:+/${pending}}"
        else
            resolved="${resolved:+${resolved}/}${component}"
        fi
    done
    [[ -x "${rootfs}/${resolved}" ]]
}

validate_rootfs() {
    local rootfs="$1"
    local contract_version
    rootfs_executable_exists "${rootfs}" /bin/bash \
        || die "exported image has no /bin/bash"
    rootfs_executable_exists "${rootfs}" /usr/local/bin/uv \
        || die "exported image has no /usr/local/bin/uv"
    rootfs_executable_exists "${rootfs}" /usr/local/cuda/bin/nvcc \
        || die "exported image has no CUDA compiler"
    contract_version="$(sed -n 's/^schema_version=//p' "${rootfs}/etc/surflo-insula-contract" | head -n 1)"
    [[ "${contract_version}" == 1 ]] \
        || die "unexpected Insula contract: ${contract_version:-missing}"
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
while ! mkdir "${LOCK}" 2>/dev/null; do
    sleep 1
done

TMP="$(mktemp -d "$(dirname -- "${DEST}")/.surflo-rootfs.XXXXXX")"
CID=""
BACKUP=""
cleanup() {
    if [[ -n "${CID}" ]]; then
        "${CONTAINER_TOOL}" rm -f "${CID}" >/dev/null 2>&1 || true
    fi
    if [[ -d "${TMP}" ]]; then
        rm -rf -- "${TMP}"
    fi
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
if [[ -n "${BACKUP}" && -e "${BACKUP}" ]]; then
    rm -rf -- "${BACKUP}"
fi

printf 'rootfs=%s\n' "${DEST}"
