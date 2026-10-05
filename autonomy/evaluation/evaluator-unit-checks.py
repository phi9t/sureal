"""Evaluator boundary fixtures inside locked CPU Insula; host setup tests separate."""
import json,unittest
from pathlib import Path
discoveries=[('/experiment/tests','test_native_detection_adapter.py'),
             ('/experiment/tests','test_detection_export.py'),
             ('/experiment/segmentation','segmentation_export_test.py'),
             ('/experiment/segmentation','camera_semantic_scoring_test.py'),
             ('/experiment/segmentation','nlz_overlap_test.py')]
suite=unittest.TestSuite()
for start,pattern in discoveries:suite.addTests(unittest.defaultTestLoader.discover(start,pattern=pattern))
result=unittest.TextTestRunner(verbosity=2).run(suite)
Path('/outputs/evaluator-unit-results.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'patterns':[pattern for _,pattern in discoveries]},indent=2)+'\n')
assert result.wasSuccessful() and not result.skipped
