FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

ARG DEBIAN_FRONTEND=noninteractive
ARG COLMAP_VERSION=3.9.1-2build2
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash ca-certificates curl git python3 python3-numpy python3-scipy \
        "colmap=${COLMAP_VERSION}" \
    && rm -rf /var/lib/apt/lists/* \
    && printf '%s\n' \
        'schema_version=1' \
        'kind=classical-geometry' \
        'ubuntu=24.04' \
        "colmap=${COLMAP_VERSION}" \
        'network_policy=build-and-fetch-only' \
        > /etc/surflo-pathway-insula

RUN mkdir -p /workspace/surflo /cache/pathway /exchange
WORKDIR /workspace/surflo
