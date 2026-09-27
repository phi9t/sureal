#!/usr/bin/env bash
set -euo pipefail

if [[ "${SURFLO_IN_INSULA:-0}" != 1 ]]; then
    echo "install_env.sh must run inside the Surflo Insula; use build.sh." >&2
    exit 2
fi

cd /workspace/surflo

CACHE="${SURFLO_INSULA_CACHE_ROOT:-/cache/surflo}"
VENV="${CACHE}/venv"
PYTHON="${VENV}/bin/python"
LOCK="experiments/insula-scout/foundation-environment.lock.json"
PYLOCK="experiments/insula-scout/pylock.foundation.toml"
VERIFY_SCRIPT="experiments/insula-scout/verify_environment_lock.py"

/usr/bin/python3 "${VERIFY_SCRIPT}" --emit-plan >/dev/null
if [[ -x "${PYTHON}" ]] \
    && /usr/bin/python3 "${VERIFY_SCRIPT}" --verify-environment "${VENV}" >/dev/null 2>&1; then
    printf 'foundation environment already matches its byte lock: %s\n' "${VENV}"
    exit 0
fi

readarray -t LOCK_VALUES < <(
    /usr/bin/python3 - "${LOCK}" <<'PY'
import json
import sys
from pathlib import Path

lock = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
python = lock["python"]
print(python["url"])
print(python["sha256"])
print(python["byte_size"])
print(python["install_path"])
for name in ("fused-ssim", "geodel"):
    source = lock["source_builds"][name]
    print(source["repository"])
    print(source["commit"])
print(lock["source_builds"]["nvdiffrast"]["commit"])
print(lock["source_builds"]["diff-gaussian-rasterization-surflo"]["tree"])
PY
)
PYTHON_URL="${LOCK_VALUES[0]}"
PYTHON_SHA256="${LOCK_VALUES[1]}"
PYTHON_BYTE_SIZE="${LOCK_VALUES[2]}"
PYTHON_ROOT="${CACHE}/${LOCK_VALUES[3]}"
FUSED_SSIM_REPOSITORY="${LOCK_VALUES[4]}"
FUSED_SSIM_COMMIT="${LOCK_VALUES[5]}"
GEODEL_REPOSITORY="${LOCK_VALUES[6]}"
GEODEL_COMMIT="${LOCK_VALUES[7]}"
NVDIFFRAST_COMMIT="${LOCK_VALUES[8]}"
RASTERIZER_TREE="${LOCK_VALUES[9]}"

mkdir -p "$(dirname -- "${PYTHON_ROOT}")"
if [[ ! -x "${PYTHON_ROOT}/bin/python3.10" ]]; then
    PYTHON_ARCHIVE="$(mktemp "${CACHE}/python-archive.XXXXXX")"
    PYTHON_STAGE="$(mktemp -d "${CACHE}/python-stage.XXXXXX")"
    curl -fsSL --retry 3 --retry-delay 2 -o "${PYTHON_ARCHIVE}" "${PYTHON_URL}"
    [[ "$(stat -c '%s' "${PYTHON_ARCHIVE}")" == "${PYTHON_BYTE_SIZE}" ]]
    printf '%s  %s\n' "${PYTHON_SHA256}" "${PYTHON_ARCHIVE}" | sha256sum -c -
    tar -xzf "${PYTHON_ARCHIVE}" -C "${PYTHON_STAGE}"
    test -x "${PYTHON_STAGE}/python/bin/python3.10"
    mv -- "${PYTHON_STAGE}/python" "${PYTHON_ROOT}"
    rm -f -- "${PYTHON_ARCHIVE}"
    rmdir -- "${PYTHON_STAGE}"
fi

BACKUP=""
cleanup_environment() {
    if [[ -n "${BACKUP}" && -d "${BACKUP}" && ! -e "${VENV}" ]]; then
        mv -- "${BACKUP}" "${VENV}"
    fi
}
trap cleanup_environment EXIT
if [[ -e "${VENV}" ]]; then
    BACKUP="$(mktemp -d "${CACHE}/venv.previous.XXXXXX")"
    rmdir -- "${BACKUP}"
    mv -- "${VENV}" "${BACKUP}"
fi
uv venv --python "${PYTHON_ROOT}/bin/python3.10" "${VENV}"
export PATH="${VENV}/bin:${PATH}"
export HF_HOME="${CACHE}/huggingface"
export TORCH_EXTENSIONS_DIR="${CACHE}/torch-extensions"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-10.0}"
export MAX_JOBS="${MAX_JOBS:-8}"

uv pip sync --python "${PYTHON}" --link-mode copy "${PYLOCK}"
uv pip install --python "${PYTHON}" --no-deps --no-build-isolation \
    -e '.[train,demo,texture]'

SOURCE_ROOT="${CACHE}/build-sources"
mkdir -p "${SOURCE_ROOT}"
fetch_locked_git() {
    local name="$1" repository="$2" commit="$3" destination stage
    destination="${SOURCE_ROOT}/${name}-${commit}"
    if [[ -d "${destination}/.git" ]] \
        && [[ "$(git -C "${destination}" rev-parse HEAD)" == "${commit}" ]] \
        && [[ -z "$(git -C "${destination}" status --porcelain=v1 --untracked-files=all)" ]]; then
        printf '%s\n' "${destination}"
        return 0
    fi
    if [[ -e "${destination}" ]]; then
        rm -rf -- "${destination}"
    fi
    stage="$(mktemp -d "${SOURCE_ROOT}/.${name}.XXXXXX")"
    git -C "${stage}" init -q || return 1
    git -C "${stage}" remote add origin "${repository}" || return 1
    git -C "${stage}" fetch -q --depth 1 origin "${commit}" || return 1
    git -C "${stage}" checkout -q --detach FETCH_HEAD || return 1
    git -C "${stage}" submodule update -q --init --recursive || return 1
    [[ "$(git -C "${stage}" rev-parse HEAD)" == "${commit}" ]] || return 1
    mv -- "${stage}" "${destination}" || return 1
    printf '%s\n' "${destination}"
}

FUSED_SSIM_SOURCE="$(fetch_locked_git fused-ssim "${FUSED_SSIM_REPOSITORY}" "${FUSED_SSIM_COMMIT}")"
GEODEL_SOURCE="$(fetch_locked_git geodel "${GEODEL_REPOSITORY}" "${GEODEL_COMMIT}")"
RASTERIZER_BUILD_SOURCE="${SOURCE_ROOT}/diff-gaussian-rasterization-surflo-${RASTERIZER_TREE}"
if [[ -e "${RASTERIZER_BUILD_SOURCE}" ]]; then
    rm -rf -- "${RASTERIZER_BUILD_SOURCE}"
fi
mkdir -p "${RASTERIZER_BUILD_SOURCE}"
git --git-dir="${SURFLO_GIT_DIR}" --work-tree="${SURFLO_GIT_WORK_TREE}" \
    archive "${RASTERIZER_TREE}" | tar -x -C "${RASTERIZER_BUILD_SOURCE}"
export SURFLO_LOCKED_ENV=1
export RASTERIZER_DIR_OVERRIDE="${RASTERIZER_BUILD_SOURCE}"
export FUSED_SSIM_DIR_OVERRIDE="${FUSED_SSIM_SOURCE}"
export GEODEL_DIR_OVERRIDE="${GEODEL_SOURCE}"
export PIP_NO_INDEX=1
bash install/build_extensions.sh --with-da3

# nvdiffrast's legacy setup.py writes build/ and *.egg-info into its source
# tree even for a non-editable install. Build it from a disposable copy so an
# Insula build never dirties the checked-out submodule.
NVDIFFRAST_BUILD_SOURCE="${SOURCE_ROOT}/nvdiffrast-${NVDIFFRAST_COMMIT}"
if [[ -e "${NVDIFFRAST_BUILD_SOURCE}" ]]; then
    rm -rf -- "${NVDIFFRAST_BUILD_SOURCE}"
fi
mkdir -p "${NVDIFFRAST_BUILD_SOURCE}"
cp -a submodules/nvdiffrast/. "${NVDIFFRAST_BUILD_SOURCE}"
uv pip install --python "${PYTHON}" --no-build-isolation --no-deps \
    "${NVDIFFRAST_BUILD_SOURCE}"

python install/verify_install.py --check-isolation
/usr/bin/python3 experiments/insula-scout/normalize_environment.py "${VENV}"

if [[ -n "${SURFLO_ENVIRONMENT_MANIFEST_OUT:-}" ]]; then
    /usr/bin/python3 "${VERIFY_SCRIPT}" --write-manifest "${SURFLO_ENVIRONMENT_MANIFEST_OUT}" \
        --environment-root "${VENV}"
else
    /usr/bin/python3 "${VERIFY_SCRIPT}" --verify-environment "${VENV}"
fi

if [[ -n "${BACKUP}" && -d "${BACKUP}" ]]; then
    rm -rf -- "${BACKUP}"
fi
BACKUP=""
trap - EXIT
