FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
ARG BAZEL_VERSION=9.2.0
ARG BAZEL_LINUX_X86_64_SHA256=7668a95db1250f12c40407251e4e203b4ec8bf39bc495d2f485b2d8c99048694
COPY requirements-tracer.lock /opt/requirements-tracer.lock
COPY requirements-test-tools.lock /opt/requirements-test-tools.lock
RUN apt-get update \
 && apt-get install -y --no-install-recommends binutils curl g++ git \
 && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir --require-hashes -r /opt/requirements-tracer.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /opt/requirements-test-tools.lock
RUN python -c "import hashlib,pathlib,urllib.request; version='${BAZEL_VERSION}'; expected='${BAZEL_LINUX_X86_64_SHA256}'; url=f'https://github.com/bazelbuild/bazel/releases/download/{version}/bazel-{version}-linux-x86_64'; data=urllib.request.urlopen(url).read(); actual=hashlib.sha256(data).hexdigest(); assert actual == expected, f'{url} sha256 {actual} != {expected}'; path=pathlib.Path('/usr/local/bin/bazel'); path.write_bytes(data); path.chmod(0o755)"
RUN bazel --version
RUN mkdir -p /experiment /source /outputs /bazel-cache
ENV PYTHONNOUSERSITE=1
