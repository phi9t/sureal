FROM python:3.10-slim-bookworm@sha256:8264197061a1abf08ccb2421281a072f60a9f18e0d15d618f5a4cb956f1e8c22
ARG BAZEL_VERSION=9.2.0
ARG BAZEL_LINUX_X86_64_SHA256=7668a95db1250f12c40407251e4e203b4ec8bf39bc495d2f485b2d8c99048694
COPY bazel-requirements.lock /opt/bazel-requirements.lock
RUN apt-get update \
    && apt-get install -y --no-install-recommends binutils g++ git \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir --require-hashes -r /opt/bazel-requirements.lock
RUN python -c "import hashlib,pathlib,urllib.request; version='${BAZEL_VERSION}'; expected='${BAZEL_LINUX_X86_64_SHA256}'; url=f'https://github.com/bazelbuild/bazel/releases/download/{version}/bazel-{version}-linux-x86_64'; data=urllib.request.urlopen(url).read(); actual=hashlib.sha256(data).hexdigest(); assert actual == expected, f'{url} sha256 {actual} != {expected}'; path=pathlib.Path('/usr/local/bin/bazel'); path.write_bytes(data); path.chmod(0o755)"
RUN bazel --version \
    && python -c "import numpy; assert numpy.__version__ == '1.26.4', numpy.__version__" \
    && git --version \
    && g++ --version \
    && ar --version
RUN mkdir -p /experiment /source /outputs
ENV PYTHONNOUSERSITE=1
