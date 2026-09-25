ARG CUDA_BASE=nvidia/cuda:13.2.1-cudnn-devel-ubuntu24.04
FROM ${CUDA_BASE}

ARG UV_VERSION=0.11.13
ARG UV_SHA256=f830ea3d38ae1492acf53cb7f2cd0f81d6ae22b42d2d7310a6c7d42c451e1a43

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        cmake \
        curl \
        g++-13 \
        gcc-13 \
        git \
        libgl1 \
        libglib2.0-0 \
        libnuma-dev \
        libsm6 \
        libxext6 \
        libxrender1 \
        make \
        ninja-build \
        openssh-client \
        patch \
        pkg-config \
        python3 \
        xz-utils \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-13 100 \
    && update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-13 100 \
    && curl -fsSL --retry 3 --retry-delay 2 \
        -o /tmp/uv.tar.gz \
        "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" \
    && printf '%s  %s\n' "${UV_SHA256}" /tmp/uv.tar.gz | sha256sum -c - \
    && mkdir -p /tmp/uv \
    && tar -xzf /tmp/uv.tar.gz -C /tmp/uv \
    && install -m 0755 "$(find /tmp/uv -type f -name uv -print -quit)" /usr/local/bin/uv \
    && rm -rf /tmp/uv /tmp/uv.tar.gz /var/lib/apt/lists/* \
    && test -x /usr/local/cuda/bin/nvcc \
    && test -f /usr/include/x86_64-linux-gnu/cudnn.h \
    && test -x /usr/local/bin/uv

RUN mkdir -p \
        /cache/surflo \
        /run/surflo-nvidia-driver \
        /workspace/surflo \
    && printf '%s\n' \
        'schema_version=1' \
        'image=nvidia/cuda:13.2.1-cudnn-devel-ubuntu24.04' \
        'repo=surflo' \
        'mount=/workspace/surflo' \
        'marker=SURFLO_IN_INSULA' \
        'cuda_toolkit=/usr/local/cuda' \
        'toolchain_gcc_major=13' \
        "uv_version=${UV_VERSION}" \
        "uv_sha256=${UV_SHA256}" \
        > /etc/surflo-insula-contract
