#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUN_ID=phase-a-v1
OVERWRITE=0
EMIT_PLAN=0
FETCH_ONLY=0
UPDATE_TRACKED=0

usage() {
    cat <<'EOF'
Usage: probe.sh [--run-id ID] [--overwrite] [--update-tracked-results] [--emit-plan]
       probe.sh --fetch-checkpoint

Publish a validated Blender episode into the shared cache and run the stock
Surflo probe offline. Checkpoint fetching is an explicit networked operation.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --run-id) RUN_ID="${2:?--run-id requires a value}"; shift 2 ;;
        --run-id=*) RUN_ID="${1#*=}"; shift ;;
        --overwrite) OVERWRITE=1; shift ;;
        --update-tracked-results) UPDATE_TRACKED=1; shift ;;
        --emit-plan) EMIT_PLAN=1; shift ;;
        --fetch-checkpoint) FETCH_ONLY=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'error: unknown argument: %s\n' "$1" >&2; exit 2 ;;
    esac
done
[[ "${RUN_ID}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || {
    printf 'error: unsafe run id: %s\n' "${RUN_ID}" >&2
    exit 2
}

EPISODE="/cache/surflo/photoreal-scenes/episodes/${RUN_ID}"
OUTPUT="/cache/surflo/photoreal-scenes/results/${RUN_ID}"
if [[ "${EMIT_PLAN}" == 1 ]]; then
    printf '{"schema_version":1,"run_id":"%s","fetch_checkpoint":%s,"publisher_network_mode":"offline","surflo_network_mode":"%s","episode":"%s","output":"%s","seeds":[0,1,2,3],"num_query_points":100000,"num_steps":100,"overwrite":%s,"update_tracked_results":%s}\n' \
        "${RUN_ID}" "$([[ "${FETCH_ONLY}" == 1 ]] && printf true || printf false)" \
        "$([[ "${FETCH_ONLY}" == 1 ]] && printf networked || printf offline)" \
        "${EPISODE}" "${OUTPUT}" \
        "$([[ "${OVERWRITE}" == 1 ]] && printf true || printf false)" \
        "$([[ "${UPDATE_TRACKED}" == 1 ]] && printf true || printf false)"
    exit 0
fi

if [[ "${FETCH_ONLY}" == 1 ]]; then
    exec "${HERE}/../insula-scout/enter.sh" --networked -- \
        /workspace/surflo/experiments/insula-scout/run_scout.sh fetch-checkpoint
fi

publish_args=(--run-id "${RUN_ID}")
[[ "${OVERWRITE}" != 1 ]] || publish_args+=(--overwrite)
"${HERE}/enter.sh" --offline -- \
    /workspace/surflo/experiments/photoreal-scenes/pipeline/inside.sh \
    publish "${publish_args[@]}"

surflo_args=(photoreal-probe --episode "${EPISODE}" --output "${OUTPUT}")
[[ "${OVERWRITE}" != 1 ]] || surflo_args+=(--overwrite)
[[ "${UPDATE_TRACKED}" != 1 ]] || surflo_args+=(
    --update-tracked-output /workspace/surflo/experiments/photoreal-scenes/results.json
)
exec "${HERE}/../insula-scout/enter.sh" --offline -- \
    /workspace/surflo/experiments/insula-scout/run_scout.sh photoreal-probe \
    "${surflo_args[@]:1}"
