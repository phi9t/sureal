#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${SURFLO_IN_INSULA:-0}" != 1 ]]; then
    exec "${HERE}/enter.sh" /workspace/surflo/experiments/insula-scout/run_scout.sh "$@"
fi

cd /workspace/surflo
CACHE="${SURFLO_INSULA_CACHE_ROOT:-/cache/surflo}"
export PATH="${CACHE}/venv/bin:${PATH}"
export HF_HOME="${CACHE}/huggingface"
export TORCH_EXTENSIONS_DIR="${CACHE}/torch-extensions"
MODEL_LOCK="experiments/photoreal-scenes/model.lock.json"
MODEL_LOCK_TOOL="experiments/photoreal-scenes/pipeline/model_lock.py"
model_field() { python "${MODEL_LOCK_TOOL}" get --lock "${MODEL_LOCK}" --field "$1"; }
CKPT_REPOSITORY="$(model_field checkpoint.repository)"
CKPT_FILENAME="$(model_field checkpoint.filename)"
CKPT="${CACHE}/$(model_field checkpoint.cache_path)"
VGGT_REPOSITORY="$(model_field vggt.repository)"
VGGT_REVISION="$(model_field vggt.revision)"
VGGT_CACHE="${CACHE}/$(model_field vggt.cache_path)"
EVAL_DATA="${CACHE}/eval-data"
EVAL_RESULTS="${CACHE}/eval-results"
SYNTHETIC_ROOT="${CACHE}/synthetic-ambiguity"
SYNTHETIC_EPISODE="${SYNTHETIC_ROOT}/episode"
SYNTHETIC_RESULTS="${SYNTHETIC_ROOT}/stock-surflo"
GPU="${CUDA_VISIBLE_DEVICES:-0}"
export CUDA_VISIBLE_DEVICES="${GPU}"

usage() {
    echo "usage: $0 {verify|sample|eval|train-smoke|fetch-checkpoint|synthetic-generate|synthetic-probe|synthetic|photoreal-probe|all}" >&2
}

verify_model_cache() {
    python "${MODEL_LOCK_TOOL}" verify \
        --lock "${MODEL_LOCK}" --cache-root "${CACHE}" >/dev/null
}

fetch_vggt() {
    hf download "${VGGT_REPOSITORY}" --revision "${VGGT_REVISION}" \
        config.json model.safetensors >/dev/null
    mkdir -p "${VGGT_CACHE}/refs"
    printf '%s' "${VGGT_REVISION}" >"${VGGT_CACHE}/refs/.main.tmp.$$"
    mv -f "${VGGT_CACHE}/refs/.main.tmp.$$" "${VGGT_CACHE}/refs/main"
    verify_model_cache
}

fetch_inputs() {
    mkdir -p "${CACHE}/checkpoints" "${EVAL_DATA}" "${EVAL_RESULTS}"
    if [[ ! -f "${CKPT}" ]]; then
        mkdir -p "$(dirname -- "${CKPT}")"
        hf download "${CKPT_REPOSITORY}" "${CKPT_FILENAME}" \
            --local-dir "$(dirname -- "${CKPT}")"
    fi
    fetch_vggt
}

verify() {
    python install/verify_install.py --check-isolation
}

sample() {
    fetch_inputs
    python scripts/infer.py mode=plain \
        ckpt="${CKPT}" \
        source.image_folder=media/sample source.n_images=16 \
        num_query_points=100000 overwrite=true \
        output_dir="${CACHE}/outputs/plain-default-16v-100k"
    python scripts/infer.py mode=guided guided=default \
        ckpt="${CKPT}" \
        source.image_folder=media/sample source.n_images=16 \
        num_query_points=100000 overwrite=true \
        output_dir="${CACHE}/outputs/guided-default-16v-100k"
}

fetch_eval_scene() {
    fetch_inputs
    if [[ ! -f "${EVAL_DATA}/tnt/16views/Ignatius/sample_0000_views_016.pt" ]]; then
        hf download AntoineGuedon/Surflo-eval-data \
            --repo-type dataset \
            --include 'tnt/16views/Ignatius/*' \
            --local-dir "${EVAL_DATA}"
    fi
}

eval_one() {
    local label="$1"
    shift
    python scripts/evaluate.py benchmarks=tnt \
        data_dir="${EVAL_DATA}/tnt/16views" \
        n_views=16 'scene_ids=[Ignatius]' limit_scenes=1 \
        output_json="${EVAL_RESULTS}/tnt-ignatius-16v-${label}.json" \
        "$@"
}

evaluate() {
    fetch_eval_scene
    eval_one plain mode=plain ckpt="${CKPT}"
    eval_one guided mode=guided guided=no_densification \
        num_query_points=200000 ckpt="${CKPT}"
    eval_one vggt predictor=vggt
    eval_one vggt-tsdf predictor=vggt use_tsdf=true
    eval_one da3 predictor=da3
    eval_one da3-tsdf predictor=da3 use_tsdf=true
}

train_smoke() {
    fetch_eval_scene
    local run_root="${CACHE}/train-smoke-8k"
    if [[ -e "${run_root}/checkpoints/checkpoint.pt" ]]; then
        if [[ -z "${SURFLO_SCOUT_RUN_ID:-}" ]]; then
            echo "Training smoke checkpoint already exists: ${run_root}/checkpoints/checkpoint.pt" >&2
            echo "Set SURFLO_SCOUT_RUN_ID to select a fresh run." >&2
            exit 2
        fi
        run_root="${CACHE}/train-smoke-8k-${SURFLO_SCOUT_RUN_ID}"
    fi
    if [[ -e "${run_root}/checkpoints/checkpoint.pt" ]]; then
        echo "Refusing to resume an existing smoke run: ${run_root}" >&2
        exit 2
    fi
    cd /workspace/surflo/training
    PYTHONPATH="/workspace/surflo/experiments/insula-scout/math_sdpa:/workspace/surflo" \
    WANDB_MODE=disabled \
    torchrun --standalone --nproc_per_node=1 train.py \
        override=full_16views \
        data_dir="${EVAL_DATA}/tnt/16views" ood_data_dir=null \
        num_val_scenes=null num_workers=0 max_img_per_gpu=16 \
        max_epochs=1 limit_train_batches=1 limit_val_batches=1 \
        ood_val_epoch_freq=null model.compile=false optim.ema.enabled=false \
        logging.viz.enabled=false logging.log_dir="${run_root}/logs" \
        checkpoint.save_dir="${run_root}/checkpoints" \
        data.val.dataset.dataset_configs.0.n_points=1024 \
        data.val.dataset.dataset_configs.0.chamfer_n_points=1024 \
        +data.val.dataset.dataset_configs.0.len_test=1
}

synthetic_generate() {
    python experiments/insula-scout/synthetic_ambiguity/episode.py \
        --output "${SYNTHETIC_EPISODE}" \
        --width 512 --height 384 \
        --context-views 16 --target-views 8 \
        --surface-points-per-box 20000 \
        --seed 20260925
}

synthetic_probe() {
    fetch_inputs
    if [[ ! -f "${SYNTHETIC_EPISODE}/manifest.json" ]]; then
        synthetic_generate
    fi
    python experiments/insula-scout/synthetic_ambiguity/probe.py \
        --episode "${SYNTHETIC_EPISODE}" \
        --checkpoint "${CKPT}" \
        --output "${SYNTHETIC_RESULTS}" \
        --seeds 0,1,2,3 \
        --query-points 100000 \
        --steps 100
}

photoreal_probe() {
    local episode=""
    local output=""
    local tracked_output=""
    local overwrite=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --episode) episode="${2:?--episode requires a value}"; shift 2 ;;
            --output) output="${2:?--output requires a value}"; shift 2 ;;
            --update-tracked-output) tracked_output="${2:?--update-tracked-output requires a value}"; shift 2 ;;
            --overwrite) overwrite=1; shift ;;
            *) echo "unknown photoreal-probe argument: $1" >&2; return 2 ;;
        esac
    done
    [[ -n "${episode}" && -n "${output}" ]] || {
        echo "photoreal-probe requires --episode and --output" >&2
        return 2
    }
    verify_model_cache
    [[ -f "${episode}/manifest.json" ]] || {
        echo "photoreal episode is missing: ${episode}" >&2
        return 2
    }
    [[ -f "${episode}/validation.json" ]] || {
        echo "photoreal episode validation is missing: ${episode}" >&2
        return 2
    }
    if [[ -e "${output}" && "${overwrite}" != 1 ]]; then
        echo "photoreal probe output already exists: ${output}; pass --overwrite" >&2
        return 2
    fi
    local output_parent output_name staging backup
    output_parent="$(dirname -- "${output}")"
    output_name="$(basename -- "${output}")"
    mkdir -p "${output_parent}"
    staging="$(mktemp -d "${output_parent}/.${output_name}.tmp.XXXXXX")"
    backup="${output_parent}/.${output_name}.old.$$"
    if [[ -e "${backup}" ]]; then
        echo "photoreal probe backup already exists: ${backup}" >&2
        rm -rf -- "${staging}"
        return 2
    fi
    local rc=0
    local measurement_date_utc
    measurement_date_utc="$(date -u +%F)"
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    python experiments/insula-scout/synthetic_ambiguity/probe.py \
        --episode "${episode}" \
        --checkpoint "${CKPT}" \
        --output "${staging}" \
        --seeds 0,1,2,3 \
        --query-points 100000 \
        --steps 100 \
        --source-recipe experiments/photoreal-scenes/recipe.json \
        --model-lock "${MODEL_LOCK}" || rc=$?
    if [[ "${rc}" != 0 ]]; then
        rm -rf -- "${staging}"
        return "${rc}"
    fi
    python experiments/photoreal-scenes/pipeline/probe_summary.py \
        --raw "${staging}/results.json" \
        --manifest "${episode}/manifest.json" \
        --validation "${episode}/validation.json" \
        --analytic-baseline experiments/insula-scout/synthetic_results.json \
        --measurement-date-utc "${measurement_date_utc}" \
        --output "${staging}/compact-results.json" || rc=$?
    if [[ "${rc}" != 0 ]]; then
        rm -rf -- "${staging}"
        return "${rc}"
    fi
    [[ ! -e "${output}" ]] || mv -- "${output}" "${backup}"
    if ! mv -- "${staging}" "${output}"; then
        [[ ! -e "${backup}" || -e "${output}" ]] || mv -- "${backup}" "${output}"
        return 1
    fi
    [[ ! -e "${backup}" ]] || rm -rf -- "${backup}"
    if [[ -n "${tracked_output}" ]]; then
        mkdir -p "$(dirname -- "${tracked_output}")"
        cp -- "${output}/compact-results.json" "${tracked_output}.tmp.$$"
        mv -f -- "${tracked_output}.tmp.$$" "${tracked_output}"
    fi
}

command="${1:-}"
case "${command}" in
    verify) verify ;;
    sample) sample ;;
    eval) evaluate ;;
    train-smoke) train_smoke ;;
    fetch-checkpoint) fetch_inputs ;;
    synthetic-generate) synthetic_generate ;;
    synthetic-probe) synthetic_probe ;;
    synthetic) synthetic_generate; synthetic_probe ;;
    photoreal-probe) shift; photoreal_probe "$@" ;;
    all) verify; sample; evaluate; train_smoke; synthetic_generate; synthetic_probe ;;
    *) usage; exit 2 ;;
esac
