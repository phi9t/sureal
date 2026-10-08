import re
import unittest
from pathlib import Path
from detection.native_detection_adapter import EXPECTED_DEFAULT_BREAKDOWNS

SOURCE=Path.home()/'.cache/waystone/waymo-perception/metrics-source/src/waymo_open_dataset/metrics/tools/compute_detection_metrics_main.cc'

class DetectionBreakdownLiveTests(unittest.TestCase):
    def test_committed_breakdowns_match_documented_native_default(self):
        if not SOURCE.exists():
            self.skipTest('native evaluator source is not available')
        documented={m.group(1) for m in re.finditer(r'^// (.+): \[mAP ([^\]]+)\] \[mAPH ([^\]]+)\]',SOURCE.read_text(),re.M)}
        self.assertEqual(documented,EXPECTED_DEFAULT_BREAKDOWNS)

if __name__=='__main__':unittest.main()
