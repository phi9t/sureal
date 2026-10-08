#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="${SURFLO_PATHWAY_CONTAINER_ENGINE:-docker}"

command -v "${ENGINE}" >/dev/null 2>&1 || {
    printf 'error: container engine not found: %s\n' "${ENGINE}" >&2
    exit 2
}

"${ENGINE}" build --network host --tag surflo-pathway-classical:1 "${HERE}/classical"
"${ENGINE}" build --network host --tag surflo-pathway-classical-mvs:1 "${HERE}/classical-mvs"
"${ENGINE}" build --network host --tag surflo-pathway-orb-slam:1 "${HERE}/orb-slam"
"${ENGINE}" build --network host --tag surflo-pathway-neural-rendering:1 "${HERE}/neural-rendering"
"${ENGINE}" build --network host --tag surflo-pathway-implicit-surface:1 "${HERE}/implicit-surface"
"${ENGINE}" build --network host --tag surflo-pathway-radiance-field:1 "${HERE}/radiance-field"
"${ENGINE}" build --network host --tag surflo-pathway-gaussian-splatting:1 --file "${HERE}/gaussian-splatting/Dockerfile" "${HERE}"

FOUNDATION_GPU="$({
    PYTHONPATH="${HERE}/../pipeline${PYTHONPATH:+:${PYTHONPATH}}" \
        python3 -c 'from contracts import selected_gpu_device; print(selected_gpu_device())'
})"
CUDA_VISIBLE_DEVICES="${FOUNDATION_GPU}" \
    SURFLO_PATHWAY_CONTAINER_ENGINE="${ENGINE}" \
    "${HERE}/../../experiments/insula-scout/build.sh"
