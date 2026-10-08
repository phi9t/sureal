"""Independent receipt closure check against current code and retained artifacts."""
import json
from pathlib import Path
from evidence.source_snapshot import file_sha256
from insula.runtime_identity import verify_rootfs


def candidate_files(experiment):
    names=['enter.sh','insula/verify_m0.py','insula/entry.py','insula/runtime_identity.py',
           'insula/m0_probe.py','insula/m0_validate.py','insula/m0_receipt.py']
    return [experiment/name for name in names]


def validate_receipt(run: Path, rootfs: Path, experiment: Path):
    receipt=json.loads((run/'receipt.json').read_text())
    if receipt['schema_version']!=1 or receipt['milestone']!='M0':raise ValueError('receipt schema')
    lock=json.loads(Path(str(rootfs)+'.lock.json').read_text())
    if receipt['runtime_lock']!=lock:raise ValueError('runtime identity mismatch')
    verify_rootfs(rootfs,lock['rootfs_sha256'])
    required={str(p.relative_to(experiment)) for p in candidate_files(experiment)}
    if set(receipt['code_hashes'])!=required:raise ValueError('incomplete candidate inventory')
    for relative,digest in receipt['code_hashes'].items():
        if file_sha256(experiment/relative)!=digest:raise ValueError('candidate changed')
    expected={'host_listener_positive_control','producer-0','validator-0','producer-1','validator-1',
              'wrong-lock','missing-rootfs','failed-assertion','failed-command'}
    logs={name+'.log' for name in expected if name!='host_listener_positive_control'}
    if set(receipt['log_hashes'])!=logs:raise ValueError('incomplete live logs')
    for name,digest in receipt['log_hashes'].items():
        if file_sha256(run/name)!=digest:raise ValueError('log changed')
    if (run/'input/sentinel').read_text()!='readonly input\n':raise ValueError('input changed')
    checks=receipt['checks']
    if len(checks)!=9 or {c['name'] for c in checks}!=expected:raise ValueError('incomplete assertions')
    for c in checks:
        if c['name']=='host_listener_positive_control':
            if c['passed'] is not True:raise ValueError('host listener not verified')
        elif c['name'].startswith(('producer','validator')):
            if c['exit_code']!=0:raise ValueError('failed live check')
            if 'PASS' not in (run/(c['name']+'.log')).read_text():raise ValueError('missing live log')
        elif c['exit_code']==0:raise ValueError('failure injection passed unexpectedly')
    for number,files in receipt['artifacts'].items():
        if set(files)!={'matrix.npy','synthetic.parquet','synthetic.png','observed.json'}:raise ValueError('artifact completeness')
        for name,digest in files.items():
            if file_sha256(run/f'run-{number}'/name)!=digest:raise ValueError('artifact changed')
    if set(receipt['artifacts'])!={'0','1'} or receipt['artifacts']['0']!=receipt['artifacts']['1']:raise ValueError('replay mismatch')
    return receipt

if __name__=='__main__':
    import sys
    validate_receipt(Path(sys.argv[1]),Path(sys.argv[2]),Path(__file__).resolve().parents[1])
    print('PASS independently reconciled M0 receipt, code, runtime, assertions and artifacts')
