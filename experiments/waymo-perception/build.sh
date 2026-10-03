#!/usr/bin/env bash
# Networked provisioning; offline execution uses enter.sh.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEST="${WAYMO_INSULA_ROOT:-${HOME}/.cache/waystone/waymo-perception/insula/rootfs-v2}"
[[ ! -e "$DEST" ]] || { printf 'error: refusing to replace existing rootfs: %s\n' "$DEST" >&2; exit 1; }
mkdir -p -- "$(dirname -- "$DEST")"
STAGE="$(mktemp -d "$(dirname -- "$DEST")/.rootfs.XXXXXX")"
CID=""
cleanup() {
    if [[ -n "$CID" ]]; then docker rm -f "$CID" >/dev/null; fi
    if [[ -n "$STAGE" ]]; then rm -rf -- "$STAGE"; fi
}
trap cleanup EXIT
docker build --platform linux/amd64 -t sureal-waymo-cpu:m0 -f "$HERE/insula/Dockerfile" "$HERE"
IMAGE="$(docker image inspect sureal-waymo-cpu:m0 --format '{{.Id}}')"
CID="$(docker create "$IMAGE" /bin/true)"
docker export "$CID" | tar -C "$STAGE" -xf -
docker rm "$CID" >/dev/null
CID=""
PYTHONPATH="$HERE" python3 - "$STAGE" "$HERE" "$IMAGE" <<'PY'
import hashlib, json, sys
from pathlib import Path
from pipeline.runtime_identity import rootfs_identity
root, here, image = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
lock = {'schema_version': 1, 'platform': 'linux/amd64', 'image_id': image,
        'rootfs_sha256': rootfs_identity(root),
        'requirements_sha256': hashlib.sha256((here/'requirements-tracer.lock').read_bytes()).hexdigest(),
        'dockerfile_sha256': hashlib.sha256((here/'insula/Dockerfile').read_bytes()).hexdigest()}
(root.parent/(root.name+'.lock.json')).write_text(json.dumps(lock, indent=2)+'\n')
PY
mv -- "$STAGE.lock.json" "$DEST.lock.json"
mv -- "$STAGE" "$DEST"
STAGE=""
printf 'rootfs=%s\nlock=%s\n' "$DEST" "$DEST.lock.json"
