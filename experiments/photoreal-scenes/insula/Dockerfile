FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG BLENDER_VERSION=4.5.14
ARG BLENDER_ARCHIVE=blender-4.5.14-linux-x64.tar.xz
ARG BLENDER_URL=https://download.blender.org/release/Blender4.5/blender-4.5.14-linux-x64.tar.xz
ARG BLENDER_SHA256=9ba871ff2ecd36526b77432745980b7e6664ecd0c7ca11c48849073dcfe06da3

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash ca-certificates curl xz-utils \
        python3 python3-numpy python3-openimageio python3-pil \
        libdbus-1-3 libegl1 libgl1 libice6 libpulse0 libsm6 \
        libwayland-client0 libx11-6 libxcursor1 libxext6 libxfixes3 libxi6 \
        libxinerama1 libxkbcommon0 libxrandr2 libxrender1 libxxf86vm1 \
    && rm -rf /var/lib/apt/lists/* \
    && curl --fail --location --retry 3 "${BLENDER_URL}" -o "/tmp/${BLENDER_ARCHIVE}" \
    && printf '%s  %s\n' "${BLENDER_SHA256}" "/tmp/${BLENDER_ARCHIVE}" | sha256sum -c - \
    && mkdir -p /opt/blender \
    && tar -xJf "/tmp/${BLENDER_ARCHIVE}" --strip-components=1 -C /opt/blender \
    && rm "/tmp/${BLENDER_ARCHIVE}" \
    && ln -s /opt/blender/blender /usr/local/bin/blender \
    && printf 'schema_version=1\nblender_version=%s\nblender_archive_sha256=%s\n' \
        "${BLENDER_VERSION}" "${BLENDER_SHA256}" \
        > /etc/photoreal-blender-insula-contract

RUN mkdir -p /workspace/surflo /cache/blender /exchange /run/photoreal-nvidia-driver
