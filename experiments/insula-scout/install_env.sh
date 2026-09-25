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
if [[ ! -x "${PYTHON}" ]]; then
    uv venv --python 3.10 --seed "${VENV}"
fi
export PATH="${VENV}/bin:${PATH}"
export HF_HOME="${CACHE}/huggingface"
export TORCH_EXTENSIONS_DIR="${CACHE}/torch-extensions"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-10.0}"
export MAX_JOBS="${MAX_JOBS:-8}"

# Surflo's released environments stop at torch 2.4 / CUDA 12.4, which cannot
# target B200 (sm_100).  This scout deliberately uses the current cu130 stack.
uv pip install --python "${PYTHON}" \
    torch==2.9.1 torchvision==0.24.1 \
    --index-url https://download.pytorch.org/whl/cu130

uv pip install --python "${PYTHON}" \
    'numpy>=1.26,<2' \
    'einops>=0.8.2,<0.9' \
    'flow-matching>=1.0.10,<2' \
    'huggingface-hub>=0.24,<2' \
    'hydra-core>=1.3.2,<1.4' \
    'omegaconf>=2.3.0,<2.4' \
    'pillow>=10,<13' \
    'safetensors>=0.4,<1' \
    'scipy>=1.15.3,<2' \
    'torch-geometric>=2.7,<2.8' \
    'tqdm>=4.67.3,<5' \
    'trimesh>=4.11.3,<5' \
    'ema-pytorch>=0.7.9,<0.9' \
    'fvcore>=0.1.5,<0.2' \
    'iopath>=0.1.9,<0.2' \
    'wandb>=0.16,<1' \
    'gradio>=4,<7' \
    'plotly>=5,<7' \
    'xatlas>=0.0.9,<0.1' \
    addict ninja setuptools wheel

uv pip install --python "${PYTHON}" torch-cluster==1.6.3 \
    --find-links https://data.pyg.org/whl/torch-2.9.0+cu130.html

# The project metadata intentionally pins the authors' tested torch range.
# Install the checkout without resolving that constraint, since torch and all
# CUDA-agnostic dependencies were selected explicitly above.
uv pip install --python "${PYTHON}" --no-deps -e '.[train,demo,texture]'

bash install/build_extensions.sh --with-da3

# nvdiffrast's legacy setup.py writes build/ and *.egg-info into its source
# tree even for a non-editable install. Build it from a disposable copy so an
# Insula build never dirties the checked-out submodule.
NVDIFFRAST_BUILD_ROOT="$(mktemp -d "${CACHE}/nvdiffrast-build.XXXXXX")"
trap 'rm -rf -- "${NVDIFFRAST_BUILD_ROOT}"' EXIT
NVDIFFRAST_BUILD_SOURCE="${NVDIFFRAST_BUILD_ROOT}/nvdiffrast"
mkdir -p "${NVDIFFRAST_BUILD_SOURCE}"
cp -a submodules/nvdiffrast/. "${NVDIFFRAST_BUILD_SOURCE}"
uv pip install --python "${PYTHON}" --no-build-isolation --no-deps \
    "${NVDIFFRAST_BUILD_SOURCE}"
rm -rf -- "${NVDIFFRAST_BUILD_ROOT}"
trap - EXIT

# DA3 uses addict without declaring it.  Its unconstrained xformers dependency
# resolves to a cu128 wheel on this stack; the DA3-LARGE models use the MLP
# fallback and were verified without xformers, so remove the incompatible wheel.
uv pip install --python "${PYTHON}" addict
uv pip uninstall --python "${PYTHON}" xformers || true

python install/verify_install.py --check-isolation
