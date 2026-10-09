import json
import tempfile
import unittest
from pathlib import Path
from evidence.source_snapshot import file_sha256
from insula.launch_plan import BAZEL_LINUX_X86_64_SHA256, BAZEL_VERSION, plan_data
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import CURRENT_CPU_ROOTFS_NAME
from insula.staging_lease import staging_lease
from detection.training_box_replay import load_pinned_runtime, replay, worker_launch_plan

AUTONOMY = Path(__file__).resolve().parents[1]

def write_rootfs(root: Path):
    root.mkdir(parents=True)
    (root/'bin').mkdir()
    (root/'bin/python').write_text('#!/bin/sh\n')
    (root/'bin/python').chmod(0o755)
    (root/'etc').mkdir()
    (root/'etc/issue').write_text('fixture rootfs\n')

def write_cpu_lock(path: Path, rootfs: Path):
    lock = {
        'schema_version': 1,
        'rootfs_sha256': rootfs_identity(rootfs),
        'dockerfile_sha256': file_sha256(AUTONOMY/'insula/Dockerfile'),
        'requirements_sha256': file_sha256(AUTONOMY/'requirements-tracer.lock'),
        'test_tools_requirements_sha256': file_sha256(AUTONOMY/'insula/cpu-test-tools-requirements.lock'),
        'bazel_version': BAZEL_VERSION,
        'bazel_linux_x86_64_sha256': BAZEL_LINUX_X86_64_SHA256,
    }
    path.write_text(json.dumps(lock, indent=2)+'\n')
    return lock

class ReplayGateTests(unittest.TestCase):
    def test_busy_queue_refused_before_output_or_runtime_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp);(cache/'scientific-processing').mkdir()
            output=cache/'result'
            with staging_lease(cache/'scientific-processing/cohort-queue.lock'):
                with self.assertRaises(ValueError):
                    replay(cache=cache,output=output,code_root=cache/'nonexistent',expected_candidate_sha256='0'*64)
            self.assertFalse(output.exists())

    def test_changed_execution_candidate_refused_before_runtime_or_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp);(cache/'scientific-processing').mkdir()
            code=cache/'code';(code/'research').mkdir(parents=True)
            (code/'research/training-box-replay-execution.candidate.json').write_text('{}')
            with self.assertRaises(ValueError):
                replay(cache=cache,output=cache/'result',code_root=code,
                       expected_candidate_sha256='0'*64)
            self.assertFalse((cache/'result').exists())

    def test_retained_raw_size_includes_unlisted_files(self):
        from detection.training_box_replay import retained_raw_bytes
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp);code=cache/'code';code.mkdir()
            root=cache/'slices/validation-two-scenes-20260929/raw';root.mkdir(parents=True)
            (root/'known.parquet').write_bytes(b'abc');(root/'extra.parquet').write_bytes(b'12345')
            (code/'dataset').mkdir()
            (code/'dataset/dataset.lock.json').write_text(json.dumps({'objects':[{'relative_path':'raw/known.parquet','size_bytes':3}]}))
            self.assertEqual(retained_raw_bytes(cache,code),8)

    def test_worker_launch_plan_uses_checked_runtime_and_named_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rootfs=root/CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock=write_cpu_lock(rootfs.with_name(rootfs.name+'.lock.json'), rootfs)
            code=root/'code';audit=root/'audit';inputs=root/'inputs';phase=root/'phase'
            for path in (code,audit,inputs,phase):
                path.mkdir()

            runtime=load_pinned_runtime(rootfs, lock)
            plan=worker_launch_plan(runtime, code_root=code, source_audit=audit,
                                    replay_inputs=inputs, output=phase,
                                    worker_job='/tmp/replay-inputs/reference.json',
                                    worker_job_sha256='a'*64, mode='reference')
            data=plan_data(plan)

            self.assertEqual(data['runtime']['form'], 'recipe-digest')
            self.assertIn(['--setenv', 'PYTHONPATH', '/experiment'], data['environment'])
            mounts={mount['role']: (mount['inside_path'], mount['mode']) for mount in data['mounts']}
            self.assertEqual(mounts['input:/tmp/source-audit'], ('/tmp/source-audit', 'read_only'))
            self.assertEqual(mounts['input:/tmp/replay-inputs'], ('/tmp/replay-inputs', 'read_only'))
            self.assertEqual(mounts['output'], ('/outputs', 'writable'))
            self.assertEqual(data['command'], ['python', '-m', 'detection.training_box_job',
                                               '--job', '/tmp/replay-inputs/reference.json',
                                               '--expected-job-sha256', 'a'*64,
                                               '--mode', 'reference',
                                               '--output', '/outputs/report.json'])

            with self.assertRaisesRegex(ValueError, 'production runtime lock changed'):
                load_pinned_runtime(rootfs, {**lock, 'rootfs_sha256': '0'*64})

    def test_worker_launch_plan_gets_overlap_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rootfs=root/CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock=write_cpu_lock(rootfs.with_name(rootfs.name+'.lock.json'), rootfs)
            code=root/'code';inputs=root/'inputs';phase=root/'phase'
            for path in (code,inputs,phase):
                path.mkdir()

            runtime=load_pinned_runtime(rootfs, lock)
            with self.assertRaisesRegex(ValueError, 'code.*input:/tmp/source-audit|input:/tmp/source-audit.*code'):
                worker_launch_plan(runtime, code_root=code, source_audit=code,
                                   replay_inputs=inputs, output=phase,
                                   worker_job='/tmp/replay-inputs/reference.json',
                                   worker_job_sha256='a'*64, mode='reference')

if __name__ == '__main__':
    unittest.main()
