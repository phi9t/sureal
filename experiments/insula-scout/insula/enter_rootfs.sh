#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${HERE}/../../.." && pwd)"
CACHE_ROOT="${SURFLO_INSULA_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/surflo/insula-scout}"
ROOTFS="${SURFLO_INSULA_ROOT:-${CACHE_ROOT}/rootfs}"
NETWORK_MODE="${SURFLO_INSULA_NETWORK:-networked}"
EMIT_PLAN=0
REPO_MOUNT=/workspace/surflo
CACHE_MOUNT=/cache/surflo
DRIVER_MOUNT=/run/surflo-nvidia-driver

usage() {
    cat <<'EOF'
Usage: enter_rootfs.sh [options] [-- command [args...]]

Enter the Surflo bubblewrap Insula with the repository and persistent cache
mounted read-write. With no command, start a login shell.

Options:
  --rootfs DIR    Use this materialized rootfs
  --cache-root DIR
                  Use this host cache directory
  --repo DIR      Mount this checkout at /workspace/surflo
  --offline       Unshare networking
  --networked     Share host networking (default)
  --emit-plan     Print the resolved launch plan as JSON without executing it
  -h, --help      Show this help
EOF
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rootfs) ROOTFS="${2:?--rootfs requires a value}"; shift 2 ;;
        --rootfs=*) ROOTFS="${1#*=}"; shift ;;
        --cache-root) CACHE_ROOT="${2:?--cache-root requires a value}"; shift 2 ;;
        --cache-root=*) CACHE_ROOT="${1#*=}"; shift ;;
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

case "${NETWORK_MODE}" in
    networked|offline) ;;
    *) die "SURFLO_INSULA_NETWORK must be networked or offline, got ${NETWORK_MODE}" ;;
esac

if [[ "${EMIT_PLAN}" == 1 ]]; then
    python3 - "${ROOTFS}" "${REPO_ROOT}" "${CACHE_ROOT}" "${NETWORK_MODE}" "$@" <<'PY'
import json
import sys

rootfs, repo, cache, network, *command = sys.argv[1:]
print(json.dumps({
    "schema_version": 1,
    "rootfs": rootfs,
    "repo_root": repo,
    "repo_mount": "/workspace/surflo",
    "host_cache_root": cache,
    "cache_mount": "/cache/surflo",
    "network_mode": network,
    "marker_env": "SURFLO_IN_INSULA",
    "command": command,
}, indent=2, sort_keys=True))
PY
    exit 0
fi

command -v bwrap >/dev/null 2>&1 || die "bwrap is required on the host"
[[ -d "${REPO_ROOT}" ]] || die "Surflo checkout not found: ${REPO_ROOT}"
[[ -x "${ROOTFS}/bin/bash" ]] || die "Surflo Insula is missing: ${ROOTFS}; run build.sh first"
contract_version="$(sed -n 's/^schema_version=//p' "${ROOTFS}/etc/surflo-insula-contract" | head -n 1)"
[[ "${contract_version}" == 1 ]] || die "unexpected Insula contract: ${contract_version:-missing}"

STATE_ROOT="${CACHE_ROOT}/state"
PASSWD_FILE="${STATE_ROOT}/passwd"
GROUP_FILE="${STATE_ROOT}/group"
mkdir -p "${CACHE_ROOT}/home" "${CACHE_ROOT}/tmp" "${STATE_ROOT}"

HOST_UID="$(id -u)"
HOST_GID="$(id -g)"
HOST_USER="$(id -un 2>/dev/null || printf surflo)"
HOST_GROUP="$(id -gn 2>/dev/null || printf surflo)"
printf 'root:x:0:0:root:/root:/bin/bash\n%s:x:%s:%s:Surflo:%s/home:/bin/bash\n' \
    "${HOST_USER}" "${HOST_UID}" "${HOST_GID}" "${CACHE_MOUNT}" >"${PASSWD_FILE}"
printf 'root:x:0:\n%s:x:%s:\n' "${HOST_GROUP}" "${HOST_GID}" >"${GROUP_FILE}"

bwrap_args=(
    --bind "${ROOTFS}" /
    --proc /proc
    --tmpfs /tmp
    --tmpfs /run
    --dir "${DRIVER_MOUNT}"
    --dev /dev
    --bind "${REPO_ROOT}" "${REPO_MOUNT}"
    --bind "${CACHE_ROOT}" "${CACHE_MOUNT}"
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
        [[ -e "${host_file}" ]] && bwrap_args+=(--ro-bind "${host_file}" "${host_file}")
    done
fi

shopt -s nullglob
for device in /dev/nvidia* /dev/nvidia-caps/*; do
    bwrap_args+=(--dev-bind "${device}" "${device}")
done
driver_paths=()
for library in \
    /usr/lib/x86_64-linux-gnu/libcuda.so* \
    /usr/lib/x86_64-linux-gnu/libnvidia-*.so* \
    /usr/lib64/libcuda.so* \
    /usr/lib64/libnvidia-*.so*; do
    driver_paths+=("${library}")
done
for library in "${driver_paths[@]}"; do
    bwrap_args+=(--ro-bind "${library}" "${DRIVER_MOUNT}/$(basename -- "${library}")")
done
shopt -u nullglob

if [[ -x /usr/bin/nvidia-smi ]]; then
    bwrap_args+=(--ro-bind /usr/bin/nvidia-smi /usr/bin/nvidia-smi)
fi
if [[ -d /nix/store ]]; then
    bwrap_args+=(--ro-bind /nix/store /nix/store)
fi

bwrap_args+=(
    --setenv PATH "${CACHE_MOUNT}/venv/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin"
    --setenv HOME "${CACHE_MOUNT}/home"
    --setenv TMPDIR "${CACHE_MOUNT}/tmp"
    --setenv CUDA_HOME /usr/local/cuda
    --setenv CUDA_PATH /usr/local/cuda
    --setenv LD_LIBRARY_PATH "${DRIVER_MOUNT}:/usr/local/cuda/lib64:/usr/local/cuda/lib"
    --setenv HF_HOME "${CACHE_MOUNT}/huggingface"
    --setenv TORCH_EXTENSIONS_DIR "${CACHE_MOUNT}/torch-extensions"
    --setenv SURFLO_INSULA_CACHE_ROOT "${CACHE_MOUNT}"
    --setenv SURFLO_IN_INSULA 1
    --setenv PYTHONNOUSERSITE 1
    --setenv USE_LIBUV 0
    --setenv NVIDIA_VISIBLE_DEVICES "${NVIDIA_VISIBLE_DEVICES:-all}"
    --setenv USER "${HOST_USER}"
)

for name in CUDA_VISIBLE_DEVICES HF_TOKEN HUGGING_FACE_HUB_TOKEN MAX_JOBS \
    SURFLO_SCOUT_RUN_ID TERM TORCH_CUDA_ARCH_LIST; do
    if [[ "${!name+x}" == x ]]; then
        bwrap_args+=(--setenv "${name}" "${!name}")
    fi
done

if [[ $# -eq 0 ]]; then
    set -- /bin/bash -l
fi
exec bwrap "${bwrap_args[@]}" "$@"
