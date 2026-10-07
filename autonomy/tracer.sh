#!/usr/bin/env bash
# Offline real-data investigation runtime; networked acquisition uses gcs/Waystone.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV="${WAYMO_TRACER_VENV:-${HOME}/.cache/waystone/waymo-perception/probe-venv}"
usage() {
    cat <<'EOF'
Usage: tracer.sh verify-env | inspect SAMPLE_ROOT OUTPUT_DIR | validate SAMPLE_ROOT OUTPUT_DIR
All commands run in an offline bubblewrap namespace with a private HOME.
WAYMO_TRACER_VENV selects the isolated, preinstalled Python environment.
See requirements-tracer.lock and research/tracer-bullet-e2e.md for setup/evidence.
EOF
}
case "${1:---help}" in
    -h|--help) usage; exit 0 ;;
    verify-env|inspect|validate) COMMAND="$1"; shift ;;
    *) usage >&2; exit 2 ;;
esac
command -v bwrap >/dev/null || { printf 'error: bwrap required\n' >&2; exit 1; }
[[ -x "${VENV}/bin/python" ]] || { printf 'error: install the tracer environment first\n' >&2; exit 1; }
VENV="$(realpath -- "$VENV")"
PYTHON_BASE="$(dirname -- "$(dirname -- "$(readlink -f -- "${VENV}/bin/python")")")"
PYTHON_REFERENCE="$(readlink -- "${VENV}/bin/python")"
[[ "$PYTHON_REFERENCE" == /* ]] || PYTHON_REFERENCE="${VENV}/bin/${PYTHON_REFERENCE}"
PYTHON_REFERENCE_BASE="$(dirname -- "$(dirname -- "$(realpath -s -- "$PYTHON_REFERENCE")")")"
args=(
    --unshare-all --die-with-parent
    --ro-bind /usr /usr --symlink usr/lib /lib --symlink usr/lib64 /lib64
    --ro-bind /etc/ld.so.cache /etc/ld.so.cache
    --ro-bind "$VENV" "$VENV" --ro-bind "$PYTHON_BASE" "$PYTHON_BASE"
    --ro-bind "$PYTHON_BASE" "$PYTHON_REFERENCE_BASE"
    --ro-bind "$HERE" /experiment
    --proc /proc --dev /dev --tmpfs /tmp
    --clearenv --setenv PATH /usr/bin:/bin --setenv HOME /tmp
    --setenv PYTHONNOUSERSITE 1
    --setenv WAYMO_TRACER_OFFLINE 1
    --setenv WAYMO_HOST_NETNS "$(readlink /proc/self/ns/net)"
    --chdir /experiment
)
if [[ "$COMMAND" == verify-env ]]; then
    [[ $# == 0 ]] || { usage >&2; exit 2; }
    exec bwrap "${args[@]}" "${VENV}/bin/python" -c '
import os, importlib.metadata as m, io, tempfile
from pathlib import Path
import pyarrow as pa, pyarrow.parquet as pq
from PIL import Image
assert os.readlink("/proc/self/ns/net") != os.environ["WAYMO_HOST_NETNS"]
assert not Path("/source").exists()
assert not Path("/data02/home/philip.yang/.cache/sureal/gcs/config").exists()
assert not any("tensorflow" in d.metadata["Name"].lower() for d in m.distributions())
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp)/"probe.parquet";pq.write_table(pa.table({"x":[1]}),p)
 assert pq.read_table(p)["x"].to_pylist()==[1]
 b=io.BytesIO();Image.new("RGB",(2,2)).save(b,format="PNG")
 assert Image.open(io.BytesIO(b.getvalue())).size==(2,2)
print("PASS: isolated imports, Parquet/image round trips, separate network namespace, no GCS credential mount")
'
fi
[[ $# == 2 ]] || { usage >&2; exit 2; }
SAMPLE="$(realpath -- "$1")"
OUTPUT="$(realpath -m -- "$2")"
if [[ "$OUTPUT" == "$SAMPLE" || "$OUTPUT" == "$SAMPLE/"* || "$SAMPLE" == "$OUTPUT/"* ]]; then
    printf 'error: source/output overlap\n' >&2; exit 1
fi
[[ "$(basename -- "$OUTPUT")" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] \
    || { printf 'error: unsafe output run name\n' >&2; exit 1; }
mkdir -p -- "$(dirname -- "$OUTPUT")"
args+=(--ro-bind "$SAMPLE" /source --bind "$(dirname -- "$OUTPUT")" /outputs)
exec bwrap "${args[@]}" "${VENV}/bin/python" -m dataset.tracer "$COMMAND" \
    --sample /source --output "/outputs/$(basename -- "$OUTPUT")"
