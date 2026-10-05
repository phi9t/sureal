import tempfile
import unittest
from pathlib import Path
from pipeline.semantic_recovery_job import recover_semantic_archive
from pipeline.staging_lease import staging_lease

class SemanticRecoveryJobGateTests(unittest.TestCase):
    def test_queue_refused_before_output_or_source_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp);working=cache/'scientific-processing';working.mkdir()
            output=working/'recovery'
            with staging_lease(working/'cohort-queue.lock'):
                with self.assertRaises(ValueError):
                    recover_semantic_archive({},cache=cache,code_root=cache/'missing',output=output)
            self.assertFalse(output.exists())
