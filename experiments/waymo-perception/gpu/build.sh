#!/usr/bin/env bash
set -euo pipefail
here="$(cd -- "$(dirname -- "$0")" && pwd)"
expected=sha256:eaf68603ced6f9abb5ee401522a07774183a8412ff3d9de61278f09c0738749d
actual="$(docker image inspect surflo-insula:cuda13.2.1-locked --format '{{.Id}}')"
[[ "$actual" == "$expected" ]] || { echo 'GPU base image identity mismatch' >&2; exit 1; }
docker build -t sureal-waymo-gpu:torch291-cu130 "$here"
