FROM ubuntu:22.04@sha256:b8b6ee6aa931ecd9d0d952abc34dc0e5f7c6a30c6bb71b079fe399fde0329c02

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential ca-certificates cmake git libboost-serialization-dev libcrypto++-dev \
        libeigen3-dev libgl1-mesa-dev libglew-dev libopencv-dev libpython3-dev \
        libssl-dev pkg-config python3 time && \
    rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/stevenlovegrove/Pangolin.git /opt/Pangolin && \
    git -C /opt/Pangolin checkout dd801d244db3a8e27b7fe8020cd751404aa818fd && \
    test "$(git -C /opt/Pangolin rev-parse HEAD)" = dd801d244db3a8e27b7fe8020cd751404aa818fd && \
    cmake -S /opt/Pangolin -B /opt/Pangolin/build -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_EXAMPLES=OFF -DBUILD_PANGOLIN_PYTHON=OFF -DBUILD_TESTS=OFF && \
    cmake --build /opt/Pangolin/build --parallel 8 && \
    cmake --install /opt/Pangolin/build

RUN git clone https://github.com/UZ-SLAMLab/ORB_SLAM3.git /opt/ORB_SLAM3 && \
    git -C /opt/ORB_SLAM3 checkout 4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4 && \
    test "$(git -C /opt/ORB_SLAM3 rev-parse HEAD)" = 4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4

COPY surflo_rgbd.cc /opt/ORB_SLAM3/Examples/RGB-D/surflo_rgbd.cc
RUN printf '\nadd_executable(surflo_rgbd Examples/RGB-D/surflo_rgbd.cc)\ntarget_link_libraries(surflo_rgbd ${PROJECT_NAME})\nset_target_properties(surflo_rgbd PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/bin)\n' >> /opt/ORB_SLAM3/CMakeLists.txt && \
    cd /opt/ORB_SLAM3 && chmod +x build.sh && ./build.sh

COPY run-rgbd.sh /opt/surflo/run-rgbd.sh
RUN chmod 0555 /opt/surflo/run-rgbd.sh && \
    printf '%s\n' \
        'schema_version=1' \
        'kind=rgbd-slam' \
        'ubuntu=22.04' \
        'orb_slam3_commit=4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4' \
        'pangolin_commit=dd801d244db3a8e27b7fe8020cd751404aa818fd' \
        'network_policy=build-and-fetch-only' \
        > /etc/surflo-pathway-insula

WORKDIR /work
