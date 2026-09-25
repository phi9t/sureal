#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SURFLO_REPO="$(cd -- "${HERE}/../.." && pwd)"
CACHE_ROOT="${SURFLO_INSULA_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/surflo/insula-scout}"
SURFLO_INSULA_ROOT="${SURFLO_INSULA_ROOT:-${CACHE_ROOT}/rootfs}"

export SURFLO_INSULA_CACHE_ROOT="${CACHE_ROOT}"
export SURFLO_INSULA_ROOT
exec "${HERE}/insula/enter_rootfs.sh" --repo "${SURFLO_REPO}" "$@"
