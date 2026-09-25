#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "${HERE}/../.." && pwd)"
CACHE_ROOT="${PHOTOREAL_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/surflo/photoreal-scenes}"
ROOTFS="${PHOTOREAL_INSULA_ROOT:-${CACHE_ROOT}/rootfs}"
EXCHANGE_ROOT="${SURFLO_SCOUT_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/surflo/insula-scout}"

export PHOTOREAL_CACHE_ROOT="${CACHE_ROOT}"
export PHOTOREAL_INSULA_ROOT="${ROOTFS}"
export SURFLO_SCOUT_CACHE_ROOT="${EXCHANGE_ROOT}"
exec "${HERE}/insula/enter_rootfs.sh" --repo "${REPO}" "$@"
