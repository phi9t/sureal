"""Admit the original frame's range inputs with independent live reconciliation."""
import json, shutil, subprocess, sys
from pathlib import Path
P = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(P), str(P / 'tier1')]
from storage import sha, unique_payload_bytes
from admission import reserve_write
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
C = Path.home() / '.cache/waystone/waymo-perception'
W = C / 'scientific-processing'
fpath = P / 'research/tier1-allclass-fixture-verified.json'
f = json.loads(fpath.read_text())
for key in ('physical', 'targets', 'report', 'boxes'):
    assert sha(f[key]) == f[key + '_sha256']
scene, timestamp = f['identity'].split(':')
baseline = Path(f['controls']['baseline']['observations']).parent
stage = C / 'scientific-processing-staging/advanced-range-source-v1'
record = json.loads((stage / 'source-record.json').read_text())
raw = stage / 'source.parquet'
assert raw.stat().st_size == record['source']['source_metadata']['size']
assert sha(raw) == record['source']['sha256']
receiptpath = P / 'research/advanced-range-fixture-verified.json'
if receiptpath.exists():
    receipt = json.loads(receiptpath.read_text())
    for path, digest in receipt['artifacts'].items():
        assert sha(path) == digest
    print('VERIFIED existing range fixture')
    sys.exit(0)
R = C / 'insula/advanced-range-fixture-v1'
R.mkdir()
source = R / 'source'
source.mkdir()
for folder in ('advanced', 'pipeline'):
    shutil.copytree(P / folder, source / folder, ignore=shutil.ignore_patterns('__pycache__'))
pins = {str(p): sha(p) for p in source.rglob('*') if p.is_file()}
root = C / 'insula/rootfs-v2'
lock = json.loads(Path(str(root) + '.lock.json').read_text())
verify_rootfs(root, lock['rootfs_sha256'])
reserve_write(W, 64 * 1024**2)
d = W / 'advanced-range-fixture-v1'
d.mkdir()
inp = d / 'input'
inp.mkdir()
job = {'scene': scene, 'timestamp': int(timestamp), 'raw_sha256': record['source']['sha256'],
       'physical_sha256': f['physical_sha256']}
(inp / 'job.json').write_text(json.dumps(job))
checks = []
for mode in ('producer', 'reference'):
    out = d / mode
    out.mkdir()
    cmd = launch_plan(root, source, stage, out,
                      ['python', '/experiment/advanced/range_cache_contract.py', mode])
    index = cmd.index('--')
    cmd[index:index] = ['--ro-bind', str(inp), '/tmp/input', '--ro-bind', f['physical'],
                        '/tmp/physical.npz', '--ro-bind', str(baseline), '/tmp/baseline']
    if mode == 'reference':
        cmd[index:index] = ['--ro-bind', str(d / 'producer'), '/tmp/produced']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    (out / 'live.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    checks.append({'command': cmd, 'exit_code': result.returncode})
assert all(sha(path) == digest for path, digest in pins.items())
assert unique_payload_bytes(W) <= 15 * 1024**3
receipt = {'identity': f['identity'], 'fixture_receipt_sha256': sha(fpath),
           'targets_sha256': f['targets_sha256'], 'all_native_ground_truth': 73,
           'raw_source_record': record, 'raw_source_record_sha256': sha(stage / 'source-record.json'),
           'observations': str(d / 'producer/observations.npz'),
           'observations_sha256': sha(d / 'producer/observations.npz'),
           'runtime_lock': lock, 'source_pins': pins, 'checks': checks,
           'validation': json.loads((d / 'reference/check.json').read_text()),
           'artifacts': {str(p): sha(p) for p in d.rglob('*') if p.is_file()}}
receiptpath.write_text(json.dumps(receipt, indent=2))
print('ADMITTED actual ten-return range fixture', flush=True)
