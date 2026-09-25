#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EMIT_PLAN=0
OVERWRITE=0
UPDATE_TRACKED=0
RUN_ID=phase-a-v1
DEVICE=""

usage() {
    cat <<'EOF'
Usage: run.sh [--emit-plan] COMMAND [options]

Commands:
  build          Build and validate the Blender Insula rootfs
  fetch          Download and hash-check locked assets (networked)
  render-draft   Render the small draft profile (offline; --device required)
  render         Render the benchmark profile (offline OptiX only)
  validate       Validate a completed or staged episode (offline)
  probe          Run stock Surflo against an episode in the Surflo Insula
  all            Build, fetch, render, validate, contact-sheet, and probe

Options:
  --run-id ID
  --device CPU|OPTIX
  --overwrite
  --update-tracked-results  Update the canonical tracked summary (probe only)
  --emit-plan     Print the resolved dispatch plan without executing it
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --emit-plan) EMIT_PLAN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) break ;;
    esac
done
COMMAND="${1:-}"
[[ -n "${COMMAND}" ]] || { usage >&2; exit 2; }
shift
while [[ $# -gt 0 ]]; do
    case "$1" in
        --run-id) RUN_ID="${2:?--run-id requires a value}"; shift 2 ;;
        --run-id=*) RUN_ID="${1#*=}"; shift ;;
        --device) DEVICE="${2:?--device requires a value}"; shift 2 ;;
        --device=*) DEVICE="${1#*=}"; shift ;;
        --overwrite) OVERWRITE=1; shift ;;
        --update-tracked-results) UPDATE_TRACKED=1; shift ;;
        *) printf 'error: unknown argument: %s\n' "$1" >&2; exit 2 ;;
    esac
done

case "${COMMAND}" in
    build) NETWORK_MODE=host; PROFILE=none; DEFAULT_DEVICE=none ;;
    fetch) NETWORK_MODE=networked; PROFILE=none; DEFAULT_DEVICE=none ;;
    render-draft) NETWORK_MODE=offline; PROFILE=draft; DEFAULT_DEVICE=OPTIX ;;
    render) NETWORK_MODE=offline; PROFILE=benchmark; DEFAULT_DEVICE=OPTIX ;;
    validate) NETWORK_MODE=offline; PROFILE=auto; DEFAULT_DEVICE=none ;;
    probe) NETWORK_MODE=offline; PROFILE=auto; DEFAULT_DEVICE=CUDA ;;
    all) NETWORK_MODE=mixed; PROFILE=benchmark; DEFAULT_DEVICE=OPTIX ;;
    *) printf 'error: unknown command: %s\n' "${COMMAND}" >&2; usage >&2; exit 2 ;;
esac
[[ -n "${DEVICE}" ]] || DEVICE="${DEFAULT_DEVICE}"
DEVICE="${DEVICE^^}"
if [[ "${PROFILE}" == benchmark && "${DEVICE}" != OPTIX ]]; then
    printf 'error: benchmark renders require --device OPTIX\n' >&2
    exit 2
fi
if [[ "${PROFILE}" == draft && "${DEVICE}" != CPU && "${DEVICE}" != OPTIX ]]; then
    printf 'error: draft renders require explicit CPU or OPTIX\n' >&2
    exit 2
fi

if [[ "${EMIT_PLAN}" == 1 ]]; then
    printf '{"schema_version":1,"command":"%s","network_mode":"%s","profile":"%s","device":"%s","run_id":"%s","overwrite":%s,"update_tracked_results":%s}\n' \
        "${COMMAND}" "${NETWORK_MODE}" "${PROFILE}" "${DEVICE}" "${RUN_ID}" \
        "$([[ "${OVERWRITE}" == 1 ]] && printf true || printf false)" \
        "$([[ "${UPDATE_TRACKED}" == 1 ]] && printf true || printf false)"
    exit 0
fi

common_args=(--run-id "${RUN_ID}" --device "${DEVICE}")
[[ "${OVERWRITE}" != 1 ]] || common_args+=(--overwrite)
case "${COMMAND}" in
    build)
        "${HERE}/build.sh"
        exec "${HERE}/../insula-scout/build.sh"
        ;;
    fetch)
        "${HERE}/enter.sh" --networked -- \
            /workspace/surflo/experiments/photoreal-scenes/pipeline/inside.sh fetch
        exec "${HERE}/probe.sh" --fetch-checkpoint
        ;;
    render-draft|render|validate)
        exec "${HERE}/enter.sh" --offline -- \
            /workspace/surflo/experiments/photoreal-scenes/pipeline/inside.sh \
            "${COMMAND}" "${common_args[@]}"
        ;;
    probe)
        probe_args=(--run-id "${RUN_ID}")
        [[ "${OVERWRITE}" != 1 ]] || probe_args+=(--overwrite)
        [[ "${UPDATE_TRACKED}" != 1 ]] || probe_args+=(--update-tracked-results)
        exec "${HERE}/probe.sh" "${probe_args[@]}"
        ;;
    all)
        "${HERE}/run.sh" build
        "${HERE}/run.sh" fetch
        render_args=(render --run-id "${RUN_ID}" --device OPTIX)
        probe_args=(probe --run-id "${RUN_ID}" --update-tracked-results)
        if [[ "${OVERWRITE}" == 1 ]]; then
            render_args+=(--overwrite)
            probe_args+=(--overwrite)
        fi
        "${HERE}/run.sh" "${render_args[@]}"
        "${HERE}/run.sh" validate --run-id "${RUN_ID}"
        "${HERE}/run.sh" "${probe_args[@]}"
        ;;
esac
