"""Refuse changed scientific values even when fresh timing is permitted."""
import copy
import importlib
import json
from pathlib import Path
import tempfile
import unittest


class LegacyValuesTests(unittest.TestCase):
    def api(self):
        try:
            return importlib.import_module('resources.legacy_values')
        except ModuleNotFoundError:
            self.fail('strict legacy parity admission has not been implemented')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old = Path(self.temp.name) / 'original'
        self.fresh = Path(self.temp.name) / 'fresh'
        self.old.mkdir(); self.fresh.mkdir()

    def reports(self, name, old, fresh):
        (self.old / name).write_text(json.dumps(old))
        (self.fresh / name).write_text(json.dumps(fresh))

    def test_literal_loss_allows_only_finite_fresh_measurements(self):
        api = self.api()
        old = {'frames': 16, 'rows': [{'loss': 2.5}], 'elapsed_seconds': 1.0,
               'peak_rss_kib': 10, 'head_hashes': {'a': 'h'}}
        fresh = dict(old, elapsed_seconds=2.0, peak_rss_kib=20)
        self.reports('check.json', old, fresh)
        api.compare_stage('literal-loss', self.old, self.fresh)
        for value in [float('nan'), float('inf'), -1, True, '1']:
            with self.subTest(value=value):
                self.reports('check.json', old, dict(fresh, elapsed_seconds=value))
                with self.assertRaises(ValueError):
                    api.compare_stage('literal-loss', self.old, self.fresh)

    def test_changed_loss_missing_fields_and_type_changes_refuse(self):
        api = self.api()
        old = {'frames': 16, 'rows': [{'loss': 2.5}], 'elapsed_seconds': 1.0,
               'peak_rss_kib': 10}
        changes = [dict(old, rows=[{'loss': 2.6}]), dict(old, frames=16.0),
                   {k: v for k, v in old.items() if k != 'peak_rss_kib'},
                   dict(old, extra='unreviewed')]
        for fresh in changes:
            with self.subTest(fresh=fresh):
                self.reports('check.json', old, fresh)
                with self.assertRaises(ValueError):
                    api.compare_stage('literal-loss', self.old, self.fresh)

    def test_export_checks_exact_all_native_groundtruth_and_prediction_bytes(self):
        api = self.api()
        old = {'frames': 16, 'native_groundtruth': 1279, 'decoder_version': 3,
               'elapsed_seconds': 1.0, 'peak_rss_kib': 10}
        self.reports('preparation.json', old, dict(old, elapsed_seconds=2.0))
        for directory in [self.old, self.fresh]:
            (directory / 'predictions.json').write_text('[{"heading": 0.4}]')
            (directory / 'groundtruth.json').write_text('[{"object_id": "73"}]')
        api.compare_stage('export', self.old, self.fresh)
        (self.fresh / 'groundtruth.json').write_text('[]')
        with self.assertRaises(ValueError):
            api.compare_stage('export', self.old, self.fresh)
        (self.fresh / 'groundtruth.json').write_bytes((self.old / 'groundtruth.json').read_bytes())
        (self.fresh / 'predictions.json').write_text('[{"heading": 0.5}]')
        with self.assertRaises(ValueError):
            api.compare_stage('export', self.old, self.fresh)

    def test_score_preserves_inherited_preparation_timing_and_all_metrics(self):
        api = self.api()
        old = {'native_groundtruth': 1279, 'elapsed_seconds': 1.0, 'peak_rss_kib': 10,
               'scoring_seconds': 300.0, 'LEVEL2_per_class': {'sign': {'APH': 0.0}}}
        fresh = dict(old, scoring_seconds=600.0)
        for directory in [self.old, self.fresh]:
            for name in ['predictions.bin', 'groundtruth.bin', 'metrics.stdout', 'metrics.stderr']:
                (directory / name).write_bytes(name.encode())
        self.reports('check.json', old, fresh)
        api.compare_stage('score', self.old, self.fresh)
        for changed in [dict(fresh, elapsed_seconds=2.0), dict(fresh, peak_rss_kib=11),
                        dict(fresh, LEVEL2_per_class={'sign': {'APH': 0.1}})]:
            self.reports('check.json', old, changed)
            with self.assertRaises(ValueError):
                api.compare_stage('score', self.old, self.fresh)
        self.reports('check.json', old, fresh)
        (self.fresh / 'groundtruth.bin').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            api.compare_stage('score', self.old, self.fresh)

    def test_proposals_and_metric_audit_have_no_ignored_fields(self):
        api = self.api()
        for stage in ['proposals', 'metrics-audit']:
            old = {'predictions': 8000, 'all_native_GT_retained': True}
            self.reports('check.json', old, old)
            if stage == 'metrics-audit':
                for directory in [self.old, self.fresh]:
                    (directory / 'metrics.stdout').write_text('APH 0.0')
            api.compare_stage(stage, self.old, self.fresh)
            self.reports('check.json', old, dict(old, predictions=7999))
            with self.assertRaises(ValueError):
                api.compare_stage(stage, self.old, self.fresh)
        with self.assertRaises(ValueError):
            api.compare_stage('unreviewed-stage', self.old, self.fresh)

    def test_native_stderr_allows_valid_logging_timestamps_only(self):
        api = self.api()
        old = {'scoring_seconds': 300.0, 'native_groundtruth': 1279}
        self.reports('check.json', old, dict(old, scoring_seconds=600.0))
        for directory in [self.old, self.fresh]:
            for name in ['predictions.bin', 'groundtruth.bin', 'metrics.stdout']:
                (directory / name).write_bytes(name.encode())
        log = ('WARNING: Logging before InitGoogleLogging() is written to STDERR\n'
               'W20261003 07:16:14.727084     5 iou.cc:172] Tiny box dim seen, return 0.0 IOU.\n'
               'b1: center_x: -14.405123797183027\nheading: 2.4806218028029026\n')
        (self.old / 'metrics.stderr').write_text(log)
        fresh = log.replace('20261003 07:16:14.727084', '20261004 22:43:03.846616')
        (self.fresh / 'metrics.stderr').write_text(fresh)
        try: api.compare_stage('score', self.old, self.fresh)
        except ValueError:
            self.fail('valid fresh logging timestamps require explicit measurement admission')
        for changed in [fresh.replace('     5 ', '     6 '),
                        fresh.replace('Tiny box', 'Huge box'),
                        fresh.replace('2.4806218028029026', '2.5806218028029026'),
                        fresh.replace('iou.cc:172', 'iou.cc:216'),
                        fresh.replace('W20261004', 'E20261004'),
                        fresh.replace('20261004 22:43:03.846616', '<logging-timestamp>'),
                        fresh.replace('iou.cc:172] ', 'malformed-location '),
                        fresh.replace('20261004 22:43:03', '20261304 22:43:03'),
                        fresh.replace('22:43:03', '99:43:03'),
                        fresh.splitlines(keepends=True)[0]]:
            with self.subTest(changed=changed):
                (self.fresh / 'metrics.stderr').write_text(changed)
                with self.assertRaises(ValueError): api.compare_stage('score', self.old, self.fresh)

    def test_duplicate_json_keys_and_absent_payload_refuse(self):
        api = self.api()
        (self.old / 'check.json').write_text('{"frames":16,"frames":15}')
        (self.fresh / 'check.json').write_text('{"frames":15}')
        with self.assertRaises(ValueError):
            api.compare_stage('proposals', self.old, self.fresh)

    def producer(self):
        return {'recipe': 'baseline', 'frames': 16, 'head_hashes': {'head-00': 'f'*64},
                'checkpoint_sha256': 'a'*64, 'cumulative_train_seconds': 1.0,
                'elapsed_seconds': 2.0, 'peak_allocated_bytes': 100, 'peak_rss_kib': 20,
                'step_records': [{'frame': 0, 'loss': 1.5, 'synchronized_seconds': 1.0}],
                'evaluation_losses': [{'frame': 0, 'total': 1.3}]}

    def test_producer_serialization_and_timings_are_not_scientific_parity(self):
        api = self.api()
        old = self.producer(); fresh = copy.deepcopy(old)
        fresh.update(checkpoint_sha256='b'*64, cumulative_train_seconds=2.0,
                     elapsed_seconds=3.0, peak_rss_kib=30)
        fresh['step_records'][0]['synchronized_seconds'] = 2.0
        api.compare_producer_reports(old, fresh)
        for change in ['loss', 'frame', 'head', 'missing-time', 'eval', 'checkpoint-hash']:
            changed = copy.deepcopy(fresh)
            if change == 'loss': changed['step_records'][0]['loss'] = 1.6
            if change == 'frame': changed['step_records'][0]['frame'] = 1
            if change == 'head': changed['head_hashes']['head-00'] = 'c'*64
            if change == 'missing-time': del changed['step_records'][0]['synchronized_seconds']
            if change == 'eval': changed['evaluation_losses'][0]['total'] = 1.4
            if change == 'checkpoint-hash': changed['checkpoint_sha256'] = 'invalid'
            with self.subTest(change=change), self.assertRaises(ValueError):
                api.compare_producer_reports(old, changed)

if __name__ == '__main__':
    unittest.main()
