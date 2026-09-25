#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${HERE}/../../.." && pwd)"
CACHE_ROOT="${PHOTOREAL_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/surflo/photoreal-scenes}"
ROOTFS="${PHOTOREAL_INSULA_ROOT:-${CACHE_ROOT}/rootfs}"
EXCHANGE_ROOT="${SURFLO_SCOUT_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/surflo/insula-scout}"
NETWORK_MODE="${PHOTOREAL_INSULA_NETWORK:-networked}"
EMIT_PLAN=0
REPO_MOUNT=/workspace/surflo
CACHE_MOUNT=/cache/blender
EXCHANGE_MOUNT=/exchange
DRIVER_MOUNT=/run/photoreal-nvidia-driver

usage() {
    cat <<'EOF'
Usage: enter_rootfs.sh [options] [-- command [args...]]

Options:
  --rootfs DIR
  --cache-root DIR
  --exchange-root DIR
  --repo DIR
  --offline
  --networked
  --emit-plan
  -h, --help
EOF
}

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rootfs) ROOTFS="${2:?--rootfs requires a value}"; shift 2 ;;
        --rootfs=*) ROOTFS="${1#*=}"; shift ;;
        --cache-root) CACHE_ROOT="${2:?--cache-root requires a value}"; shift 2 ;;
        --cache-root=*) CACHE_ROOT="${1#*=}"; shift ;;
        --exchange-root) EXCHANGE_ROOT="${2:?--exchange-root requires a value}"; shift 2 ;;
        --exchange-root=*) EXCHANGE_ROOT="${1#*=}"; shift ;;
        --repo) REPO_ROOT="${2:?--repo requires a value}"; shift 2 ;;
        --repo=*) REPO_ROOT="${1#*=}"; shift ;;
        --offline) NETWORK_MODE=offline; shift ;;
        --networked) NETWORK_MODE=networked; shift ;;
        --emit-plan) EMIT_PLAN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; break ;;
        -*) die "unknown argument: $1" ;;
        *) break ;;
    esac
done

json_quote() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//$'\n'/\\n}"
    printf '"%s"' "${value}"
}

if [[ "${EMIT_PLAN}" == 1 ]]; then
    printf '{\n  "schema_version": 1,\n  "rootfs": '
    json_quote "${ROOTFS}"
    printf ',\n  "repo_root": '
    json_quote "${REPO_ROOT}"
    printf ',\n  "repo_mount": "/workspace/surflo",\n  "host_cache_root": '
    json_quote "${CACHE_ROOT}"
    printf ',\n  "cache_mount": "/cache/blender",\n  "host_exchange_root": '
    json_quote "${EXCHANGE_ROOT}"
    printf ',\n  "exchange_mount": "/exchange",\n  "network_mode": '
    json_quote "${NETWORK_MODE}"
    printf ',\n  "marker_env": "PHOTOREAL_IN_INSULA",\n  "command": ['
    separator=""
    for argument in "$@"; do
        printf '%s' "${separator}"
        json_quote "${argument}"
        separator=', '
    done
    printf ']\n}\n'
    exit 0
fi

[[ "${NETWORK_MODE}" == networked || "${NETWORK_MODE}" == offline ]] \
    || die "network mode must be networked or offline"
command -v bwrap >/dev/null 2>&1 || die "bwrap is required on the host"
[[ -d "${REPO_ROOT}" ]] || die "Surflo checkout not found: ${REPO_ROOT}"
[[ -x "${ROOTFS}/opt/blender/blender" ]] \
    || die "Blender Insula is missing: ${ROOTFS}; run build first"
"${HERE}/build_rootfs.sh" --validate-rootfs "${ROOTFS}" >/dev/null

STATE_ROOT="${CACHE_ROOT}/state"
PASSWD_FILE="${STATE_ROOT}/passwd"
GROUP_FILE="${STATE_ROOT}/group"
mkdir -p "${CACHE_ROOT}/home" "${CACHE_ROOT}/tmp" "${STATE_ROOT}" "${EXCHANGE_ROOT}"
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"
HOST_USER="$(id -un 2>/dev/null || printf photoreal)"
HOST_GROUP="$(id -gn 2>/dev/null || printf photoreal)"
printf 'root:x:0:0:root:/root:/bin/bash\n%s:x:%s:%s:Photoreal:%s/home:/bin/bash\n' \
    "${HOST_USER}" "${HOST_UID}" "${HOST_GID}" "${CACHE_MOUNT}" >"${PASSWD_FILE}"
printf 'root:x:0:\n%s:x:%s:\n' "${HOST_GROUP}" "${HOST_GID}" >"${GROUP_FILE}"

bwrap_args=(
    --ro-bind "${ROOTFS}" /
    --proc /proc
    --tmpfs /tmp
    --tmpfs /run
    --dir "${DRIVER_MOUNT}"
    --dev /dev
    --ro-bind "${REPO_ROOT}" "${REPO_MOUNT}"
    --bind "${CACHE_ROOT}" "${CACHE_MOUNT}"
    --bind "${EXCHANGE_ROOT}" "${EXCHANGE_MOUNT}"
    --ro-bind "${PASSWD_FILE}" /etc/passwd
    --ro-bind "${GROUP_FILE}" /etc/group
    --unshare-all
    --die-with-parent
    --chdir "${REPO_MOUNT}"
    --clearenv
)
if [[ "${NETWORK_MODE}" == networked ]]; then
    bwrap_args+=(--share-net)
    for host_file in /etc/resolv.conf /etc/hosts; do
        [[ ! -e "${host_file}" ]] || bwrap_args+=(--ro-bind "${host_file}" "${host_file}")
    done
fi

shopt -s nullglob
for device in /dev/nvidia* /dev/nvidia-caps/*; do
    bwrap_args+=(--dev-bind "${device}" "${device}")
done
for library in \
    /usr/lib/x86_64-linux-gnu/libcuda.so* \
    /usr/lib/x86_64-linux-gnu/libnvoptix.so* \
    /usr/lib/x86_64-linux-gnu/libnvidia-*.so* \
    /usr/lib64/libcuda.so* \
    /usr/lib64/libnvoptix.so* \
    /usr/lib64/libnvidia-*.so*; do
    bwrap_args+=(--ro-bind "${library}" "${DRIVER_MOUNT}/$(basename -- "${library}")")
done
shopt -u nullglob
[[ ! -x /usr/bin/nvidia-smi ]] \
    || bwrap_args+=(--ro-bind /usr/bin/nvidia-smi "${DRIVER_MOUNT}/nvidia-smi")
bwrap_args+=(
    --setenv PATH "${DRIVER_MOUNT}:/opt/blender:/usr/local/bin:/usr/bin:/bin"
    --setenv HOME "${CACHE_MOUNT}/home"
    --setenv TMPDIR "${CACHE_MOUNT}/tmp"
    --setenv LD_LIBRARY_PATH "${DRIVER_MOUNT}"
    --setenv PHOTOREAL_CACHE_ROOT "${CACHE_MOUNT}"
    --setenv PHOTOREAL_ASSET_ROOT "${CACHE_MOUNT}/assets"
    --setenv PHOTOREAL_RUN_ROOT "${CACHE_MOUNT}/runs"
    --setenv PHOTOREAL_EXCHANGE_ROOT "${EXCHANGE_MOUNT}"
    --setenv PHOTOREAL_IN_INSULA 1
    --setenv PYTHONNOUSERSITE 1
    --setenv USER "${HOST_USER}"
)
for name in CUDA_VISIBLE_DEVICES NVIDIA_VISIBLE_DEVICES TERM; do
    [[ "${!name+x}" != x ]] || bwrap_args+=(--setenv "${name}" "${!name}")
done
[[ $# -ne 0 ]] || set -- /bin/bash -l
exec bwrap "${bwrap_args[@]}" "$@"
