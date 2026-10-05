import tempfile
import unittest
from pathlib import Path
from insula.staging_lease import staging_lease
from pipeline.training_box_replay import replay

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
        import json
        from pipeline.training_box_replay import retained_raw_bytes
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp);code=cache/'code';code.mkdir()
            root=cache/'slices/validation-two-scenes-20260929/raw';root.mkdir(parents=True)
            (root/'known.parquet').write_bytes(b'abc');(root/'extra.parquet').write_bytes(b'12345')
            (code/'dataset').mkdir()
            (code/'dataset/dataset.lock.json').write_text(json.dumps({'objects':[{'relative_path':'raw/known.parquet','size_bytes':3}]}))
            self.assertEqual(retained_raw_bytes(cache,code),8)
