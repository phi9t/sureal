FROM nvidia/cuda:12.9.1-devel-ubuntu24.04@sha256:e542739fcaa4f45da5add8c4cf5769783a61628b2518304a5bbe4ace468b8c8f AS builder

ARG DEBIAN_FRONTEND=noninteractive
ARG COLMAP_GIT_COMMIT=be5e29168d4aff238409d60424812df66aac919f
ARG CUDA_ARCHITECTURES=100
ENV QT_XCB_GL_INTEGRATION=xcb_egl

RUN apt-get update \
    && apt-get install -y \
        git cmake ninja-build build-essential \
        libboost-program-options-dev libboost-graph-dev libboost-system-dev \
        libeigen3-dev libopenimageio-dev openimageio-tools libmetis-dev libgoogle-glog-dev \
        libgtest-dev libgmock-dev libsqlite3-dev libglew-dev \
        qt6-base-dev libqt6opengl6-dev libqt6openglwidgets6 qt6-svg-dev \
        libcgal-dev libceres-dev libcurl4-openssl-dev libssl-dev libmkl-full-dev \
    && rm -rf /var/lib/apt/lists/*

# Ubuntu's OpenImageIO CMake config references this optional OpenCV include
# directory even though COLMAP does not use OpenImageIO's OpenCV integration.
RUN mkdir -p /usr/include/opencv4

RUN git clone --filter=blob:none https://github.com/colmap/colmap.git /opt/colmap \
    && cd /opt/colmap \
    && git fetch origin "${COLMAP_GIT_COMMIT}" \
    && git checkout --detach "${COLMAP_GIT_COMMIT}" \
    && test "$(git rev-parse HEAD)" = "${COLMAP_GIT_COMMIT}"

RUN cmake -S /opt/colmap -B /opt/colmap/build -GNinja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES}" \
        -DCMAKE_INSTALL_PREFIX=/colmap-install \
        -DBLA_VENDOR=Intel10_64lp \
    && cmake --build /opt/colmap/build --target install --parallel

FROM nvidia/cuda:12.9.1-runtime-ubuntu24.04@sha256:1199283a7fd5fc7dcb472ea4c6b6d8eb378ef8c0b9aae5e731491c01a219ca43

ARG DEBIAN_FRONTEND=noninteractive
ARG COLMAP_GIT_COMMIT=be5e29168d4aff238409d60424812df66aac919f
ARG CUDA_ARCHITECTURES=100
RUN apt-get update \
    && apt-get install -y --no-install-recommends --no-install-suggests \
        libboost-program-options1.83.0 libc6 libomp5 libopengl0 libmetis5 \
        libceres4t64 libopenimageio2.4t64 libgcc-s1 libgl1 libglew2.2 \
        libgoogle-glog0v6t64 libqt6core6t64 libqt6gui6t64 libqt6widgets6t64 \
        libqt6openglwidgets6t64 libqt6svg6 libcurl4t64 libssl3t64 \
        libmkl-locale libmkl-intel-lp64 libmkl-intel-thread libmkl-core time \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /colmap-install/ /usr/local/
RUN printf '%s\n' "${COLMAP_GIT_COMMIT}" > /etc/surflo-pathway-colmap-commit \
    && printf '%s\n' \
        'schema_version=1' \
        'kind=classical-mvs' \
        'ubuntu=24.04' \
        'cuda=12.9.1' \
        "cuda_architectures=${CUDA_ARCHITECTURES}" \
        'colmap=4.2.0' \
        "colmap_commit=${COLMAP_GIT_COMMIT}" \
        'network_policy=build-and-fetch-only' \
        > /etc/surflo-pathway-insula

ENV QT_QPA_PLATFORM=offscreen
WORKDIR /work
