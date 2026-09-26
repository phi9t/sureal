FROM nvidia/cuda:13.2.1-cudnn-devel-ubuntu24.04@sha256:6435dc5a825b0095648d87a3c91240fd7788a85fafaf215739544d389ab74366

ARG DEBIAN_FRONTEND=noninteractive
ARG UV_VERSION=0.11.13
ARG UV_SHA256=f830ea3d38ae1492acf53cb7f2cd0f81d6ae22b42d2d7310a6c7d42c451e1a43
ARG DEPTH_ANYTHING_V2_COMMIT=a561b849ebae10a6f5ef49e26c83cbbcd36c71bf
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git python3 time xz-utils \
    && curl -fsSL --retry 3 --retry-delay 2 \
        -o /tmp/uv.tar.gz \
        "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" \
    && printf '%s  %s\n' "${UV_SHA256}" /tmp/uv.tar.gz | sha256sum -c - \
    && mkdir -p /tmp/uv \
    && tar -xzf /tmp/uv.tar.gz -C /tmp/uv \
    && install -m 0755 "$(find /tmp/uv -type f -name uv -print -quit)" /usr/local/bin/uv \
    && rm -rf /tmp/uv /tmp/uv.tar.gz /var/lib/apt/lists/* \
    && printf '%s\n' \
        'schema_version=1' \
        'kind=neural-rendering' \
        'cuda=13.2.1' \
        "uv=${UV_VERSION}" \
        'torch=2.10.0+cu130' \
        'torchvision=0.25.0+cu130' \
        "depth_anything_v2_commit=${DEPTH_ANYTHING_V2_COMMIT}" \
        'network_policy=build-and-fetch-only' \
        > /etc/surflo-pathway-insula

RUN git init /opt/depth-anything-v2 \
    && git -C /opt/depth-anything-v2 remote add origin https://github.com/DepthAnything/Depth-Anything-V2.git \
    && git -C /opt/depth-anything-v2 fetch --depth 1 origin "${DEPTH_ANYTHING_V2_COMMIT}" \
    && git -C /opt/depth-anything-v2 checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/depth-anything-v2 rev-parse HEAD)" = "${DEPTH_ANYTHING_V2_COMMIT}" \
    && rm -rf /opt/depth-anything-v2/.git \
    && printf '%s\n' "${DEPTH_ANYTHING_V2_COMMIT}" > /etc/surflo-depth-anything-v2-commit \
    && uv venv --python python3 /opt/depth-venv \
    && uv pip install --python /opt/depth-venv/bin/python \
        --index-url https://download.pytorch.org/whl/cu130 \
        torch==2.10.0 torchvision==0.25.0 \
    && uv pip install --python /opt/depth-venv/bin/python \
        numpy==2.4.3 opencv-python-headless==4.13.0.92 \
    && /opt/depth-venv/bin/python -c \
        'import cv2, numpy, torch, torchvision; assert torch.__version__.startswith("2.10.0+"); assert torchvision.__version__.startswith("0.25.0+")'

ENV PATH="/opt/depth-venv/bin:${PATH}"
ENV PYTHONPATH="/opt/depth-anything-v2/metric_depth"

RUN mkdir -p /workspace/surflo /cache/pathway /exchange /run/pathway-nvidia-driver
WORKDIR /workspace/surflo
