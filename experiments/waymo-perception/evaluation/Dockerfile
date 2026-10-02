FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake protobuf-compiler libprotobuf-dev libabsl-dev libgoogle-glog-dev libgtest-dev libssl-dev zlib1g-dev && rm -rf /var/lib/apt/lists/*
COPY upstream /upstream
COPY CMakeLists.txt /build-recipe/CMakeLists.txt
RUN mkdir -p /generated /experiment /source /outputs && protoc -I/upstream/src -I/usr/include --cpp_out=/generated $(find /upstream/src/waymo_open_dataset -name '*.proto') && cmake -S /build-recipe -B /metrics-build && cmake --build /metrics-build --parallel 8
