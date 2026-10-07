"""Serialization is admissible only with all-state/head equality and time math."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import torch


class CompareStateTests(unittest.TestCase):
    def api(self):
        try:
            return importlib.import_module('resources.compare_state')
        except ModuleNotFoundError:
            self.fail('external-pinned state/head parity worker is not implemented')

    def pin(self, path):
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = {'identity': {'recipe': 'baseline'}, 'steps': 1, 'frame_cursor': 1,
                      'training_seconds': 2.0, 'model': {'w': torch.tensor([1.5])},
                      'optimizer': {'state': {0: {'exp_avg': torch.tensor([.5])}}},
                      'rng': {'python': (1, 2), 'numpy': (torch.tensor([7]),),
                              'torch': torch.tensor([3], dtype=torch.uint8),
                              'cuda': [torch.tensor([9], dtype=torch.uint8)]}}
        self.job = {'schema_version': 1, 'prior_report': None,
                    'original_heads': {}, 'fresh_heads': {}}
        for side in ['original', 'fresh']:
            directory = self.root / side; directory.mkdir()
            state = copy.deepcopy(self.state)
            if side == 'fresh': state['training_seconds'] = 3.0
            torch.save(state, directory / 'checkpoint.pt')
            self.job[side + '_checkpoint'] = self.pin(directory / 'checkpoint.pt')
            heads = self.job[side + '_heads']
            for index in range(16):
                name = 'frame-%02d.npz' % index
                np.savez(directory / name, heat=np.array([index], dtype=np.float32))
                heads[name] = self.pin(directory / name)
            report = {'updates': 1, 'frame_cursor': 1, 'recipe': 'baseline',
                      'checkpoint_sha256': self.job[side + '_checkpoint']['sha256'],
                      'head_hashes': {name: pin['sha256'] for name, pin in heads.items()},
                      'cumulative_train_seconds': state['training_seconds'],
                      'elapsed_seconds': 5.0, 'peak_allocated_bytes': 100,
                      'peak_rss_kib': 20, 'evaluation_losses': [{'total': 1.3}],
                      'step_records': [{'step': 1, 'frame': 0, 'loss': 1.5,
                                        'synchronized_seconds': state['training_seconds']}]}
            (directory / 'check.json').write_text(json.dumps(report))
            self.job[side + '_report'] = self.pin(directory / 'check.json')

    def change_state(self, change):
        path = Path(self.job['fresh_checkpoint']['path'])
        state = torch.load(path, weights_only=True); change(state); torch.save(state, path)
        self.job['fresh_checkpoint'] = self.pin(path)
        report_path = Path(self.job['fresh_report']['path'])
        report = json.loads(report_path.read_text())
        report['checkpoint_sha256'] = self.job['fresh_checkpoint']['sha256']
        report_path.write_text(json.dumps(report)); self.job['fresh_report'] = self.pin(report_path)

    def test_all_state_and_sixteen_heads_equal_with_fresh_measured_time(self):
        result = self.api().compare(self.job)
        self.assertEqual(result['heads_compared'], 16)
        self.assertTrue(result['all_state_except_training_seconds_exact'])
        self.assertEqual(result['fresh_synchronized_seconds'], 3.0)

    def test_repinned_model_adam_rng_and_cursor_corruptions_refuse(self):
        api = self.api()
        changes = [lambda x: x['model']['w'].add_(.1),
                   lambda x: x['optimizer']['state'][0]['exp_avg'].add_(.1),
                   lambda x: x['rng']['torch'].add_(1),
                   lambda x: x['rng']['cuda'][0].add_(1),
                   lambda x: x.update(frame_cursor=2)]
        for change in changes:
            self.change_state(change)
            with self.assertRaises(ValueError): api.compare(self.job)
            self.change_state(lambda x: x.update(copy.deepcopy(dict(self.state, training_seconds=3.0))))

    def test_changed_state_time_fails_even_when_report_still_pinned(self):
        self.change_state(lambda x: x.update(training_seconds=3.1))
        with self.assertRaises(ValueError): self.api().compare(self.job)

    def test_external_pin_and_missing_head_refuse(self):
        api = self.api(); job = copy.deepcopy(self.job)
        job['fresh_checkpoint']['sha256'] = '0'*64
        with self.assertRaises(ValueError): api.compare(job)
        job = copy.deepcopy(self.job); del job['fresh_heads']['frame-15.npz']
        with self.assertRaises(ValueError): api.compare(job)

    def test_repinned_head_and_report_cannot_hide_prediction_change(self):
        path = Path(self.job['fresh_heads']['frame-15.npz']['path'])
        np.savez(path, heat=np.array([16], dtype=np.float32))
        self.job['fresh_heads']['frame-15.npz'] = self.pin(path)
        report_path = Path(self.job['fresh_report']['path'])
        report = json.loads(report_path.read_text())
        report['head_hashes']['frame-15.npz'] = self.pin(path)['sha256']
        report_path.write_text(json.dumps(report)); self.job['fresh_report'] = self.pin(report_path)
        with self.assertRaises(ValueError): self.api().compare(self.job)

    def test_changed_interval_sum_and_prior_time_refuse(self):
        report_path = Path(self.job['fresh_report']['path'])
        report = json.loads(report_path.read_text())
        report['step_records'][0]['synchronized_seconds'] = 2.0
        report_path.write_text(json.dumps(report)); self.job['fresh_report'] = self.pin(report_path)
        with self.assertRaises(ValueError): self.api().compare(self.job)
        report['step_records'][0]['synchronized_seconds'] = 3.0
        report_path.write_text(json.dumps(report)); self.job['fresh_report'] = self.pin(report_path)
        prior = self.root / 'prior.json'; prior.write_text('{"cumulative_train_seconds":1.0}')
        self.job['prior_report'] = self.pin(prior)
        with self.assertRaises(ValueError): self.api().compare(self.job)

if __name__ == '__main__':
    unittest.main()
