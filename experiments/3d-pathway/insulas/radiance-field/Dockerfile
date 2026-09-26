FROM nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04@sha256:24c8e3581ea6330038b0d374920721983312627f8adbfcf390bdb4b399d280ed

ARG NERFSTUDIO_COMMIT=50e0e3c70c775e89333256213363badbf074f29d
ARG TCNN_COMMIT=0109538c37ac0bf613f2bac8de6cda48352feca7
ENV DEBIAN_FRONTEND=noninteractive \
    PATH=/opt/venv/bin:${PATH} \
    TCNN_CUDA_ARCHITECTURES=100 \
    TORCH_CUDA_ARCH_LIST=10.0 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential ca-certificates cmake git libgl1 libglib2.0-0 libgomp1 \
      ninja-build python3 python3-dev python3-venv time \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv \
 && python -m pip install --no-cache-dir --upgrade pip==25.2 setuptools==80.9.0 wheel==0.45.1 \
 && python -m pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cu128 \
      torch==2.7.1 torchvision==0.22.1

RUN mkdir -p /opt/src/nerfstudio \
 && git -C /opt/src/nerfstudio init \
 && git -C /opt/src/nerfstudio remote add origin https://github.com/nerfstudio-project/nerfstudio.git \
 && git -C /opt/src/nerfstudio fetch --depth 1 origin "${NERFSTUDIO_COMMIT}" \
 && git -C /opt/src/nerfstudio checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/src/nerfstudio rev-parse HEAD)" = "${NERFSTUDIO_COMMIT}" \
 && python -m pip install --no-cache-dir /opt/src/nerfstudio

RUN git clone --recursive https://github.com/NVlabs/tiny-cuda-nn.git /opt/src/tiny-cuda-nn \
 && git -C /opt/src/tiny-cuda-nn checkout --detach "${TCNN_COMMIT}" \
 && git -C /opt/src/tiny-cuda-nn submodule update --init --recursive \
 && test "$(git -C /opt/src/tiny-cuda-nn rev-parse HEAD)" = "${TCNN_COMMIT}" \
 && TCNN_CUDA_ARCHITECTURES=100 python -m pip install --no-cache-dir /opt/src/tiny-cuda-nn/bindings/torch

# Nerfstudio's pinned pil_to_numpy implementation calls the pre-Pillow-12
# private encoder signature. Keep that compatibility dependency explicit.
RUN python -m pip install --no-cache-dir --force-reinstall Pillow==11.1.0

RUN printf '%s\n' \
      'schema_version=1' \
      'kind=radiance-field' \
      'cuda=12.8.1' \
      'python=3.12' \
      'torch=2.7.1+cu128' \
      'torchvision=0.22.1+cu128' \
      'pillow=11.1.0' \
      "nerfstudio_commit=${NERFSTUDIO_COMMIT}" \
      "tiny_cuda_nn_commit=${TCNN_COMMIT}" \
      'tcnn_cuda_architectures=100' \
      'network_policy=build-and-fetch-only' \
      > /etc/surflo-pathway-insula

RUN python - <<'PY'
import torch
import torchvision
import nerfstudio
import PIL
assert torch.__version__ == "2.7.1+cu128", torch.__version__
assert torchvision.__version__ == "0.22.1+cu128", torchvision.__version__
assert PIL.__version__ == "11.1.0", PIL.__version__
PY

WORKDIR /work
