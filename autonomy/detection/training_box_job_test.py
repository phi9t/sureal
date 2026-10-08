"""Synthetic full-size metadata admission; these are not scientific source results."""
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

from detection.training_box_job import run_training_box_job
from evidence.source_snapshot import file_sha256


COMPONENTS = ['camera_box', 'camera_calibration', 'camera_hkp', 'camera_image', 'camera_segmentation',
              'camera_to_lidar_box_association', 'lidar', 'lidar_box', 'lidar_calibration',
              'lidar_camera_projection', 'lidar_camera_synced_box', 'lidar_hkp', 'lidar_pose',
              'lidar_segmentation', 'projected_lidar_box', 'stats', 'vehicle_pose']


class NativeBoxJobTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.audit = self.root / 'audit'
        self.audit.mkdir()
        self.train = [f'train-{i:03}' for i in range(64)]
        self.manifest = {'scenes': {s: {'official_split': 'training', 'research_splits': ['train']}
                                    for s in self.train}, 'components': COMPONENTS,
                         'hdfs_root': 'hdfs://fixture/perception/v2.0.1/raw'}
        self.manifest['scenes'].update({f'dev-{i}': {'official_split': 'training', 'research_splits': ['development']}
                                        for i in range(8)})
        self.manifest['scenes'].update({f'val-{i}': {'official_split': 'validation', 'research_splits': ['validation']}
                                        for i in range(31)})
        self.cohort = {'dataset': 'perception-v2.0.1', 'excluded_engineering_segments': ['engineering'],
                       'cohorts': {'train': list(self.train)}}
        self.headers, self.payloads, self.pins = [], [], {}
        for index, scene in enumerate(self.train):
            table = pa.table({'key.segment_context_name': [scene], 'key.frame_timestamp_micros': [123],
                             'key.laser_object_id': ['actor'], '[LiDARBoxComponent].type': [1],
                             '[LiDARBoxComponent].box.center.x': [0.], '[LiDARBoxComponent].box.center.y': [0.],
                             '[LiDARBoxComponent].box.center.z': [12.], '[LiDARBoxComponent].box.size.x': [6.],
                             '[LiDARBoxComponent].box.size.y': [3.], '[LiDARBoxComponent].box.size.z': [2.],
                             '[LiDARBoxComponent].box.heading': [.1]})
            if index:
                table = table.slice(0, 0)
            buffer = pa.BufferOutputStream()
            pq.write_table(table, buffer)
            payload = buffer.getvalue().to_pybytes()
            digest = hashlib.sha256(payload).hexdigest()
            md5 = base64.b64encode(hashlib.md5(payload).digest()).decode()
            self.headers.append({'scene': scene, 'bytes': len(payload), 'native_rows': table.num_rows,
                                 'sha256': digest, 'md5_base64': md5})
            self.payloads.append(payload)
            self.pins[scene] = {}
            for component in COMPONENTS:
                relative = f'training/{component}/{scene}.parquet'
                component_sha = digest if component == 'lidar_box' else hashlib.sha256(relative.encode()).hexdigest()
                record = {'scene': scene, 'component': component, 'official_split': 'training',
                          'research_splits': ['train'], 'sha256': component_sha,
                          'hdfs_roundtrip_sha256': component_sha,
                          'hdfs_uri': self.manifest['hdfs_root'] + '/' + relative,
                          'source_metadata': {'generation': '1', 'size': len(payload) if component == 'lidar_box' else 1,
                                              'storage_url': 'gs://waymo_open_dataset_v_2_0_1/' + relative + '#1',
                                              'md5_hash': md5},
                          'inventory': {'rows': table.num_rows if component == 'lidar_box' else 0}}
                path = self.audit / f'training-{component}-{scene}.json'
                self.save(path, record)
                self.pins[scene][component] = self.sha(path)
        self.acquisition = self.root / 'acquisition.json'
        self.cohort_path = self.root / 'cohort.json'
        self.save(self.acquisition, self.manifest)
        self.save(self.cohort_path, self.cohort)
        self.job = {'schema_version': 1, 'acquisition': {'path': str(self.acquisition), 'sha256': self.sha(self.acquisition)},
                    'cohort': {'path': str(self.cohort_path), 'sha256': self.sha(self.cohort_path)},
                    'source_audit_root': str(self.audit), 'scene_order': self.train,
                    'source_receipt_hashes': self.pins}
        self.job_path = self.root / 'job.json'
        self.output = self.root / 'producer.json'
        self.save(self.job_path, self.job)

    def sha(self, path):
        return file_sha256(path)

    def save(self, path, value):
        Path(path).write_text(json.dumps(value, indent=2) + '\n')

    def packet(self):
        return b''.join(json.dumps(header).encode() + b'\n' + payload
                        for header, payload in zip(self.headers, self.payloads)) + b'{"kind":"end","sources":64}\n'

    def run_job(self, mode='producer', packet=None, output=None):
        stream, acknowledgements = io.BytesIO(self.packet() if packet is None else packet), io.StringIO()
        result = run_training_box_job(
            self.job_path, expected_job_sha256=self.sha(self.job_path), mode=mode,
            source_stream=stream, acknowledgement_stream=acknowledgements,
            output_path=self.output if output is None else output)
        return result, stream, acknowledgements

    def assert_refuses_before_payload(self):
        stream, acknowledgements = io.BytesIO(self.packet()), io.StringIO()
        with self.assertRaises(ValueError):
            run_training_box_job(self.job_path, expected_job_sha256=self.sha(self.job_path),
                                 mode='producer', source_stream=stream,
                                 acknowledgement_stream=acknowledgements, output_path=self.output)
        self.assertEqual(stream.tell(), 0)
        self.assertEqual(acknowledgements.getvalue(), '')
        self.assertFalse(self.output.exists())

    def test_full_synthetic_source_admission_producer_then_independent_reference(self):
        producer, _, acknowledgements = self.run_job()
        self.assertEqual(producer['completed_sources'], self.train)
        self.assertEqual(producer['rows'], 1)
        self.assertEqual(producer['worker_resources']['rss_scope'], 'worker_process_peak')
        self.assertGreater(producer['worker_resources']['peak_rss_kib'], 0)
        self.assertEqual(producer['classes']['1']['median_length_width_height_center_z'], [6., 3., 2., 12.])
        self.assertEqual(len(acknowledgements.getvalue().splitlines()), 64)
        self.job['reported'] = {'path': str(self.output), 'sha256': self.sha(self.output)}
        self.save(self.job_path, self.job)
        reference, _, reference_ack = self.run_job('reference', output=self.root / 'reference.json')
        self.assertEqual(reference['completed_sources'], 64)
        self.assertEqual(reference['native_rows'], 1)
        self.assertEqual(len(reference_ack.getvalue().splitlines()), 64)

    def test_wrong_job_hash_and_changed_manifest_refused_before_payload(self):
        with self.assertRaises(ValueError):
            run_training_box_job(self.job_path, expected_job_sha256='0' * 64, mode='producer',
                                 source_stream=io.BytesIO(self.packet()), acknowledgement_stream=io.StringIO(),
                                 output_path=self.output)
        self.acquisition.write_text(self.acquisition.read_text() + ' ')
        self.assert_refuses_before_payload()

    def test_missing_extra_duplicate_training_selection_refused(self):
        for order in [self.train[:-1], self.train + ['dev-0'], self.train[:-1] + [self.train[0]]]:
            self.job['scene_order'] = order
            self.save(self.job_path, self.job)
            self.assert_refuses_before_payload()

    def test_engineering_exclusion_and_cohort_membership_refused(self):
        self.cohort['excluded_engineering_segments'].append(self.train[0])
        self.save(self.cohort_path, self.cohort)
        self.job['cohort']['sha256'] = self.sha(self.cohort_path)
        self.save(self.job_path, self.job)
        self.assert_refuses_before_payload()
        self.cohort['excluded_engineering_segments'] = ['engineering']
        self.cohort['cohorts']['train'] = self.train[:-1] + ['dev-0']
        self.save(self.cohort_path, self.cohort)
        self.job['cohort']['sha256'] = self.sha(self.cohort_path)
        self.save(self.job_path, self.job)
        self.assert_refuses_before_payload()

    def test_missing_component_and_changed_receipt_refused(self):
        removed = self.job['source_receipt_hashes'][self.train[0]].pop('camera_image')
        self.save(self.job_path, self.job)
        self.assert_refuses_before_payload()
        self.job['source_receipt_hashes'][self.train[0]]['camera_image'] = removed
        self.save(self.job_path, self.job)
        receipt = self.audit / f'training-camera_image-{self.train[0]}.json'
        receipt.write_text(receipt.read_text() + ' ')
        self.assert_refuses_before_payload()

    def test_hash_valid_but_conflicting_source_identity_refused(self):
        receipt = self.audit / f'training-camera_image-{self.train[0]}.json'
        record = json.loads(receipt.read_text())
        record['research_splits'] = ['development']
        self.save(receipt, record)
        self.job['source_receipt_hashes'][self.train[0]]['camera_image'] = self.sha(receipt)
        self.save(self.job_path, self.job)
        self.assert_refuses_before_payload()

    def test_payload_fault_and_late_footer_failure_leave_no_report(self):
        for packet in [self.packet()[:100], self.packet().rsplit(b'{"kind":"end"', 1)[0]]:
            with self.subTest(length=len(packet)), self.assertRaises(ValueError):
                self.run_job(packet=packet)
            self.assertFalse(self.output.exists())

    def test_bad_reference_and_existing_output_never_replaced(self):
        producer, _, _ = self.run_job()
        producer['classes']['1']['median_length_width_height_center_z'][3] = 0.
        self.save(self.output, producer)
        self.job['reported'] = {'path': str(self.output), 'sha256': self.sha(self.output)}
        self.save(self.job_path, self.job)
        with self.assertRaises(ValueError):
            self.run_job('reference', output=self.root / 'reference.json')
        self.assertFalse((self.root / 'reference.json').exists())
        previous = self.output.read_bytes()
        with self.assertRaises(ValueError):
            self.run_job()
        self.assertEqual(self.output.read_bytes(), previous)

    def test_cli_roles_run_in_separate_processes_without_reference_loading_producer(self):
        arguments = ['--job', str(self.job_path), '--expected-job-sha256', self.sha(self.job_path),
                     '--mode', 'producer', '--output', str(self.output)]
        producer = subprocess.run([sys.executable, '-m', 'detection.training_box_job', *arguments],
                                  input=self.packet(), capture_output=True)
        self.assertEqual(producer.returncode, 0, producer.stderr.decode())
        self.assertEqual(len(producer.stdout.splitlines()), 64)
        producer_report = json.loads(self.output.read_text())
        self.assertEqual(producer_report['rows'], 1)
        self.job['reported'] = {'path': str(self.output), 'sha256': self.sha(self.output)}
        self.save(self.job_path, self.job)
        reference_output = self.root / 'reference-cli.json'
        arguments = ['--job', str(self.job_path), '--expected-job-sha256', self.sha(self.job_path),
                     '--mode', 'reference', '--output', str(reference_output)]
        script = ("import runpy,sys; sys.argv=['detection.training_box_job',*sys.argv[1:]]; "
                  "runpy.run_module('detection.training_box_job',run_name='__main__'); "
                  "assert 'detection.training_box_sources' not in sys.modules; "
                  "assert 'detection.training_box_statistics' not in sys.modules")
        reference = subprocess.run([sys.executable, '-c', script, *arguments],
                                   input=self.packet(), capture_output=True)
        self.assertEqual(reference.returncode, 0, reference.stderr.decode())
        self.assertEqual(len(reference.stdout.splitlines()), 64)
        self.assertEqual(json.loads(reference_output.read_text())['completed_sources'], 64)

    def test_reference_rejects_matching_statistics_with_wrong_producer_provenance_before_payload(self):
        producer, _, _ = self.run_job()
        for field in ['mode', 'acquisition_sha256', 'cohort_sha256', 'source_receipt_hashes']:
            candidate = json.loads(json.dumps(producer))
            if field == 'mode':
                candidate['job_identity'][field] = 'reference'
            elif field == 'source_receipt_hashes':
                candidate['job_identity'][field][self.train[0]]['camera_image'] = '0' * 64
            else:
                candidate['job_identity'][field] = '0' * 64
            self.save(self.output, candidate)
            self.job['reported'] = {'path': str(self.output), 'sha256': self.sha(self.output)}
            self.save(self.job_path, self.job)
            stream, acknowledgements = io.BytesIO(self.packet()), io.StringIO()
            output = self.root / f'bad-reference-{field}.json'
            with self.subTest(field=field), self.assertRaises(ValueError):
                run_training_box_job(self.job_path, expected_job_sha256=self.sha(self.job_path),
                                     mode='reference', source_stream=stream,
                                     acknowledgement_stream=acknowledgements, output_path=output)
            self.assertEqual(stream.tell(), 0)
            self.assertEqual(acknowledgements.getvalue(), '')
            self.assertFalse(output.exists())

    def test_full_job_sender_handshake_reopens_all64_sources_per_role(self):
        from contextlib import contextmanager
        from detection.training_box_sender import send_training_box_sources
        release_log=[]
        payload_by_scene=dict(zip(self.train,self.payloads))
        for role in ['producer','reference']:
            output=self.output if role=='producer' else self.root/'reference-sender.json'
            if role=='reference':
                self.job['reported']={'path':str(self.output),'sha256':self.sha(self.output)}
                self.save(self.job_path,self.job)
            @contextmanager
            def stage(source):
                # Fresh reader per source and per pass; no producer decoded data.
                release_log.append(('enter',role,source['scene']))
                try:yield io.BytesIO(payload_by_scene[source['scene']])
                finally:release_log.append(('release',role,source['scene']))
            script=("import runpy,sys;sys.argv=['detection.training_box_job',*sys.argv[1:]];"
                    "runpy.run_module('detection.training_box_job',run_name='__main__');"
                    + ("assert 'detection.training_box_sources' not in sys.modules;"
                       "assert 'detection.training_box_statistics' not in sys.modules" if role=='reference' else ""))
            command=[sys.executable,'-c',script,'--job',str(self.job_path),
                     '--expected-job-sha256',self.sha(self.job_path),'--mode',role,'--output',str(output)]
            from detection.training_box_process import run_source_worker
            result=run_source_worker(command,self.headers,stage=stage,
                                     stderr_path=self.root/(role+'-stderr.log'),
                                     ack_timeout_seconds=10,write_timeout_seconds=10,
                                     exit_timeout_seconds=10)
            self.assertEqual(result['exit_code'],0)
            self.assertEqual([e['scene'] for e in result['acknowledgements']],self.train)
            self.assertEqual(len(release_log),128 if role=='producer' else 256)
            self.assertTrue(output.is_file())
        self.assertEqual(json.loads((self.root/'reference-sender.json').read_text())['completed_sources'],64)


if __name__ == '__main__':
    unittest.main()
