FROM nvidia/cuda:13.2.1-cudnn-devel-ubuntu24.04@sha256:6435dc5a825b0095648d87a3c91240fd7788a85fafaf215739544d389ab74366

ARG DEBIAN_FRONTEND=noninteractive
ARG UV_VERSION=0.11.13
ARG UV_SHA256=f830ea3d38ae1492acf53cb7f2cd0f81d6ae22b42d2d7310a6c7d42c451e1a43
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git python3 xz-utils \
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
        'network_policy=build-and-fetch-only' \
        > /etc/surflo-pathway-insula

RUN mkdir -p /workspace/surflo /cache/pathway /exchange /run/pathway-nvidia-driver
WORKDIR /workspace/surflo
