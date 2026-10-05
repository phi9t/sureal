FROM nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04@sha256:24c8e3581ea6330038b0d374920721983312627f8adbfcf390bdb4b399d280ed

ARG NERFSTUDIO_COMMIT=50e0e3c70c775e89333256213363badbf074f29d
ARG GSPLAT_COMMIT=4d3a3b69db4de0326f983ccf7b7b255271a17b01
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

COPY radiance-field/requirements.lock.txt /etc/surflo-pathway-requirements.lock.txt
COPY radiance-field/resolved-requirements.lock.txt /etc/surflo-pathway-resolved-requirements.lock.txt
RUN python -m pip install --no-cache-dir \
      --requirement /etc/surflo-pathway-requirements.lock.txt

RUN mkdir -p /opt/src/nerfstudio \
 && git -C /opt/src/nerfstudio init \
 && git -C /opt/src/nerfstudio remote add origin https://github.com/nerfstudio-project/nerfstudio.git \
 && git -C /opt/src/nerfstudio fetch --depth 1 origin "${NERFSTUDIO_COMMIT}" \
 && git -C /opt/src/nerfstudio checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/src/nerfstudio rev-parse HEAD)" = "${NERFSTUDIO_COMMIT}" \
 && python -m pip install --no-cache-dir --no-deps /opt/src/nerfstudio

RUN mkdir -p /opt/src/gsplat \
 && git -C /opt/src/gsplat init \
 && git -C /opt/src/gsplat remote add origin https://github.com/nerfstudio-project/gsplat.git \
 && git -C /opt/src/gsplat fetch --depth 1 origin "${GSPLAT_COMMIT}" \
 && git -C /opt/src/gsplat checkout --detach FETCH_HEAD \
 && git -C /opt/src/gsplat submodule update --init --recursive \
 && test "$(git -C /opt/src/gsplat rev-parse HEAD)" = "${GSPLAT_COMMIT}" \
 && python -m pip install --no-cache-dir --no-deps --no-build-isolation --force-reinstall /opt/src/gsplat

RUN git clone --recursive https://github.com/NVlabs/tiny-cuda-nn.git /opt/src/tiny-cuda-nn \
 && git -C /opt/src/tiny-cuda-nn checkout --detach "${TCNN_COMMIT}" \
 && git -C /opt/src/tiny-cuda-nn submodule update --init --recursive \
 && test "$(git -C /opt/src/tiny-cuda-nn rev-parse HEAD)" = "${TCNN_COMMIT}" \
 && TCNN_CUDA_ARCHITECTURES=100 python -m pip install --no-cache-dir --no-deps /opt/src/tiny-cuda-nn/bindings/torch \
 && python -m pip check \
 && python -m pip freeze --all > /etc/surflo-pathway-resolved-requirements.txt \
 && sed 's#^gsplat @ file:///opt/src/gsplat$#gsplat==1.4.0#' \
      /etc/surflo-pathway-resolved-requirements.txt > /tmp/resolved-normalized.txt \
 && cmp /etc/surflo-pathway-resolved-requirements.lock.txt /tmp/resolved-normalized.txt \
 && rm /tmp/resolved-normalized.txt

RUN printf '%s\n' \
      'schema_version=1' \
      'kind=gaussian-splatting' \
      'cuda=12.8.1' \
      'python=3.12' \
      'torch=2.7.1+cu128' \
      'torchvision=0.22.1+cu128' \
      'pillow=11.1.0' \
      "nerfstudio_commit=${NERFSTUDIO_COMMIT}" \
      "gsplat_commit=${GSPLAT_COMMIT}" \
      'gsplat_version=1.4.0' \
      'torch_cuda_arch_list=10.0' \
      'requirements_lock_sha256=02c623f2a636dd774dda048f1a08c8d936d0701f74d3f50b3a7916d2280ed65a' \
      'resolved_requirements_sha256=587350cc8d7a65840facd27ebcf6fabc43f1e09d4f82541efa851ae914631076' \
      'network_policy=build-and-fetch-only' \
      > /etc/surflo-pathway-insula

COPY gaussian-splatting/run-splatfacto.py /usr/local/bin/run-splatfacto.py
RUN chmod 0555 /usr/local/bin/run-splatfacto.py \
 && python -m py_compile /usr/local/bin/run-splatfacto.py \
 && python - <<'PY'
import gsplat
import importlib.metadata
import json
import PIL
import torch
import torchvision
assert gsplat.__version__ == "1.4.0", gsplat.__version__
direct_url = json.loads(importlib.metadata.distribution("gsplat").read_text("direct_url.json"))
assert direct_url == {"dir_info": {}, "url": "file:///opt/src/gsplat"}, direct_url
assert torch.__version__ == "2.7.1+cu128", torch.__version__
assert torchvision.__version__ == "0.22.1+cu128", torchvision.__version__
assert PIL.__version__ == "11.1.0", PIL.__version__
PY

WORKDIR /work
