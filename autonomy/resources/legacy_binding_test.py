"""Changing only outputs must still bind to the same original worker/input argv."""
import copy
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from resources.sources import sha
from resources import stage_test


class LegacyBindingTests(unittest.TestCase):
    def api(self):
        try: return importlib.import_module('resources.legacy_binding')
        except ModuleNotFoundError: self.fail('legacy execution identity binding is not implemented')

    def pin(self, path): return {'path': str(path), 'sha256': sha(path)}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.current, self.pins, self.fresh, proof = stage_test.ResourceStageTests().fixture(self.root)
        self.original = self.root / 'original'; self.original.mkdir()
        self.report = {'frames': 16, 'rows': [{'loss': 2.5}], 'elapsed_seconds': 1.0, 'peak_rss_kib': 10}
        (self.original / 'check.json').write_text(json.dumps(self.report))
        (self.fresh / 'check.json').write_text(json.dumps(dict(self.report, elapsed_seconds=2.0)))
        cmd = proof['original_command'].copy(); cmd[cmd.index('/outputs')-1] = str(self.original)
        native = {'stage': 'literal-loss-1000', 'requested_stage': 'literal-loss-1000',
                  'command': cmd, 'output_directory': str(self.original)}
        self.native_path = self.root / 'literal-loss-1000-verified.json'
        self.native_path.write_text(json.dumps(native))
        self.proof_path = self.root / 'attempt/resource-admitted.json'
        self.proof_path.write_text(json.dumps(proof))
        self.entry = {'requested_stage': 'literal-loss-1000', 'native_parent': self.pin(self.native_path),
                      'proof': self.pin(self.proof_path), 'actual_command': proof['command'],
                      'output_artifacts': {str(p): sha(p) for p in self.fresh.iterdir()},
                      'resource_admission': proof['resource_admission']}
        self.entry_path = self.root / 'comparison.json'
        self.save_entry()

    def save_entry(self): self.entry_path.write_text(json.dumps(self.entry))

    def validate(self):
        return self.api().validate_cpu(self.pin(self.native_path), self.pin(self.entry_path),
                                      current_sources=self.current, source_pins=self.pins,
                                      cap_bytes=1024**3, timeout=10)

    def test_exact_native_output_replacement_and_report_parity_bind(self):
        value = self.validate()
        self.assertEqual(value['requested_stage'], 'literal-loss-1000')
        self.assertEqual(value['native_receipt'], self.pin(self.native_path))
        self.assertEqual(value['resource_proof'], self.pin(self.proof_path))

    def test_repinned_changed_scientific_report_still_refuses(self):
        (self.fresh / 'check.json').write_text(json.dumps(dict(self.report, rows=[{'loss': 2.6}])))
        self.entry['output_artifacts'][str(self.fresh / 'check.json')] = sha(self.fresh / 'check.json')
        self.save_entry()
        with self.assertRaises(ValueError): self.validate()

    def test_proof_from_another_worker_or_output_cannot_bind(self):
        self.entry['actual_command'][-1] = '/experiment/other.py'; self.save_entry()
        with self.assertRaises(ValueError): self.validate()
        self.entry['actual_command'][-1] = '/experiment/worker.py'
        self.entry['native_parent']['sha256'] = '0'*64; self.save_entry()
        with self.assertRaises(ValueError): self.validate()

    def test_omitted_fresh_evidence_and_changed_original_argv_refuse(self):
        del self.entry['output_artifacts'][str(self.fresh / 'check.json')]; self.save_entry()
        with self.assertRaises(ValueError): self.validate()
        self.entry['output_artifacts'][str(self.fresh / 'check.json')] = sha(self.fresh / 'check.json')
        native = json.loads(self.native_path.read_text()); native['command'][-1] = '/experiment/foreign.py'
        self.native_path.write_text(json.dumps(native)); self.entry['native_parent'] = self.pin(self.native_path)
        self.save_entry()
        with self.assertRaises(ValueError): self.validate()

if __name__ == '__main__':
    unittest.main()
