"""Evaluator boundary fixtures inside locked CPU Insula; host setup tests separate."""
import json,unittest
from pathlib import Path
patterns=['test_native_detection_adapter.py','test_detection_export.py','test_segmentation_export.py','test_camera_semantic_scoring.py','test_nlz_overlap.py']
suite=unittest.TestSuite()
for pattern in patterns:suite.addTests(unittest.defaultTestLoader.discover('/experiment/tests',pattern=pattern))
result=unittest.TextTestRunner(verbosity=2).run(suite)
Path('/outputs/evaluator-unit-results.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'patterns':patterns},indent=2)+'\n')
assert result.wasSuccessful() and not result.skipped
