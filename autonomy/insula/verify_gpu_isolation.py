#!/usr/bin/env python3
"""Independent GPU isolation checks through a fresh GPU launch plan."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import subprocess
import sys

from evidence.source_snapshot import file_sha256 as sha
from insula.launch_plan import build_plan, load_runtime_lock, record_plan, render_plan
from insula.runtime_roots import current_gpu_rootfs, default_lock


HERE = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".cache/waystone/waymo-perception"
GPU_INDEX = 1


def load_gpu_runtime(cache: Path = CACHE):
    rootfs = current_gpu_rootfs(Path(cache))
    return load_runtime_lock(rootfs, default_lock(rootfs))


def gpu_isolation_plan(runtime, *, output: Path, source: Path, network_probe_port: int):
    code = f"""
import os,json,socket,subprocess
from pathlib import Path
assert os.environ['HOME']=='/tmp/private-home'
assert not any(k in os.environ for k in ['GOOGLE_APPLICATION_CREDENTIALS','AWS_SECRET_ACCESS_KEY','INSULA_HOST_SECRET'])
assert not Path('/root/.config/gcloud').exists()
assert not Path('/dev/nvidia0').exists() and Path('/dev/nvidia1').exists()
for path in ['/source/forbidden-write','/experiment/forbidden-write','/etc/forbidden-write']:
    try:Path(path).write_text('unsafe')
    except OSError:pass
    else:raise AssertionError('readonly mount writable: '+path)
Path('/outputs/writable-check').write_text('ok')
s=socket.socket();s.settimeout(1)
try:s.connect(('127.0.0.1',{network_probe_port}))
except OSError:pass
else:raise AssertionError('host network reachable')
finally:s.close()
validator=['/opt/waymo/bin/python','/experiment/insula/validate_gpu_probe.py']
p=subprocess.run(validator+['/outputs/gpu-probe.json','/outputs/numeric-verified.json'],capture_output=True,text=True)
assert p.returncode==0,p.stderr
original=json.loads(Path('/outputs/gpu-probe.json').read_text())
for field in ['y','input_gradient','weight_gradient']:
    value=json.loads(json.dumps(original));value['analytic'][field][0][0]+=1
    Path('/outputs/tampered.json').write_text(json.dumps(value))
    result=subprocess.run(validator+['/outputs/tampered.json','/outputs/never-promote.json'],capture_output=True,text=True)
    assert result.returncode!=0 and not Path('/outputs/never-promote.json').exists()
Path('/outputs/isolation.json').write_text(json.dumps({{'assertions':['host positive network control then offline rejection','private HOME and absent credentials','single physical GPU mount','source/experiment/root readonly','output writable','independent numeric checker','three numerical tamper failures']}}))
print('PASS isolation and numerical failure injections')
"""
    return build_plan(
        runtime,
        code=HERE,
        source=Path(source),
        output=Path(output),
        gpu_index=GPU_INDEX,
        command=["/opt/waymo/bin/python", "-c", code],
    )


def validate_candidate(candidate: Path) -> dict:
    receipt = json.loads((candidate / "receipt.json").read_text())
    assert receipt["exit_code"] == 0
    for name, digest in receipt["candidate_hashes"].items():
        assert sha(HERE / name) == digest
    for name, digest in receipt["artifacts"].items():
        assert sha(candidate / name) == digest
    return receipt


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if len(argv) != 1:
        raise SystemExit("usage: verify_gpu_isolation.py OUTPUT_DIR")
    candidate = CACHE / "gpu-live-d"
    candidate_receipt = validate_candidate(candidate)
    output = Path(argv[0]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "gpu-probe.json").write_bytes((candidate / "gpu-probe.json").read_bytes())

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(2)
    port = listener.getsockname()[1]
    with socket.create_connection(("127.0.0.1", port), timeout=1):
        pass
    live, _ = listener.accept()
    live.close()

    runtime = load_gpu_runtime()
    plan = gpu_isolation_plan(
        runtime,
        output=output,
        source=candidate,
        network_probe_port=port,
    )
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(
            render_plan(plan),
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "INSULA_HOST_SECRET": "must-not-enter"},
        )
    finally:
        listener.close()
    (output / "live.stdout").write_text(result.stdout)
    (output / "live.stderr").write_text(result.stderr)
    record = {
        "stage": "gpu-independent-isolation",
        "candidate_receipt_sha256": sha(candidate / "receipt.json"),
        "candidate_launch_plan": candidate_receipt.get("launch_plan"),
        "started_utc": started,
        "ended_utc": datetime.now(timezone.utc).isoformat(),
        "launch_plan": record_plan(plan),
        "exit_code": result.returncode,
        "code_hashes": {
            str(path.relative_to(HERE)): sha(path)
            for path in [Path(__file__), HERE / "insula/validate_gpu_probe.py"]
        },
        "artifacts": {path.name: sha(path) for path in output.iterdir() if path.is_file()},
    }
    (output / "receipt.json").write_text(json.dumps(record, indent=2) + "\n")
    print(result.stdout, result.stderr, flush=True)
    assert result.returncode == 0, "isolation checks failed"


if __name__ == "__main__":
    main()
