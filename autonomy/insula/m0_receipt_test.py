"""Tamper checks against real recorded evidence (no runtime mocking)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from evidence.source_snapshot import file_sha256
from insula.launch_plan import BAZEL_LINUX_X86_64_SHA256, BAZEL_VERSION
from insula.m0_receipt import candidate_files, receipt_fixture_paths, validate_receipt
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import CURRENT_CPU_ROOTFS_NAME

HERE=Path(__file__).resolve().parents[1]
ROOT,EVIDENCE=receipt_fixture_paths(os.environ)

EXPECTED_CHECKS={'host_listener_positive_control','producer-0','validator-0','producer-1','validator-1',
              'wrong-lock','missing-rootfs','failed-assertion','failed-command'}

def write_runtime_lock(lock_path,rootfs,**overrides):
    lock={
        'schema_version':1,
        'rootfs_sha256':rootfs_identity(rootfs),
        'dockerfile_sha256':file_sha256(HERE/'insula/Dockerfile'),
        'requirements_sha256':file_sha256(HERE/'requirements-tracer.lock'),
        'test_tools_requirements_sha256':file_sha256(HERE/'insula/cpu-test-tools-requirements.lock'),
        'bazel_version':BAZEL_VERSION,
        'bazel_linux_x86_64_sha256':BAZEL_LINUX_X86_64_SHA256,
    }
    lock.update(overrides)
    lock_path.write_text(json.dumps(lock))
    return lock

def write_receipt_fixture(root,lock):
    experiment=root/'experiment'
    for path in candidate_files(experiment):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(str(path.relative_to(experiment))+'\n')
    run=root/'run'
    (run/'input').mkdir(parents=True)
    (run/'input/sentinel').write_text('readonly input\n')
    checks=[{'name':'host_listener_positive_control','port':1234,'passed':True}]
    for name in sorted(EXPECTED_CHECKS-{'host_listener_positive_control'}):
        log_text='PASS\n' if name.startswith(('producer','validator')) else 'expected failure\n'
        (run/(name+'.log')).write_text(log_text)
        checks.append({'name':name,'command':['true'],'exit_code':0 if log_text=='PASS\n' else 1,'expected':0})
    artifacts={}
    for number in range(2):
        phase=run/f'run-{number}'
        phase.mkdir()
        artifacts[str(number)]={}
        for name in ['matrix.npy','synthetic.parquet','synthetic.png','observed.json']:
            path=phase/name
            path.write_text(name+'\n')
            artifacts[str(number)][name]=file_sha256(path)
    receipt={
        'schema_version':1,
        'milestone':'M0',
        'runtime_lock':lock,
        'code_hashes':{str(path.relative_to(experiment)):file_sha256(path)
                       for path in candidate_files(experiment)},
        'log_hashes':{path.name:file_sha256(path) for path in run.glob('*.log')},
        'checks':checks,
        'artifacts':artifacts,
    }
    (run/'receipt.json').write_text(json.dumps(receipt))
    return run,experiment

class ReceiptTests(unittest.TestCase):
    def test_receipt_fixture_paths_accept_live_gate_environment(self):
        root,evidence=receipt_fixture_paths({
            'WAYMO_INSULA_ROOT':'/tmp/current-rootfs',
            'WAYMO_M0_RECEIPT':'/tmp/current-receipt',
        })
        self.assertEqual(root,Path('/tmp/current-rootfs'))
        self.assertEqual(evidence,Path('/tmp/current-receipt'))

    def test_valid_live_receipt(self):
        validate_receipt(EVIDENCE,ROOT,HERE)

    def test_tampered_log(self):
        self.check_mutation(lambda r,p:(p/'producer-0.log').write_text('PASS forged'))

    def check_mutation(self, mutate):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';shutil.copytree(EVIDENCE,run)
            r=json.loads((run/'receipt.json').read_text());mutate(r,run)
            (run/'receipt.json').write_text(json.dumps(r))
            with self.assertRaises(ValueError):validate_receipt(run,ROOT,HERE)

    def test_empty_candidate_inventory(self):
        self.check_mutation(lambda r,p:r.update(code_hashes={}))

    def test_missing_assertion(self):
        self.check_mutation(lambda r,p:r['checks'].pop())

    def test_tampered_artifact(self):
        self.check_mutation(lambda r,p:(p/'run-0/matrix.npy').write_bytes(b'wrong'))

    def test_omitted_expected_artifact(self):
        self.check_mutation(lambda r,p:r['artifacts']['0'].pop('matrix.npy'))

    def test_runtime_lock_is_loaded_through_strict_module_checker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rootfs=root/CURRENT_CPU_ROOTFS_NAME
            rootfs.mkdir()
            lock_path=rootfs.with_name(rootfs.name+'.lock.json')
            lock=write_runtime_lock(lock_path,rootfs,dockerfile_sha256='0'*64)
            run,experiment=write_receipt_fixture(root,lock)
            with self.assertRaisesRegex(ValueError,'dockerfile_sha256'):
                validate_receipt(run,rootfs,experiment)

if __name__ == '__main__':
    unittest.main()
