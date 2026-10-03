import unittest
from balanced_gate import validate_balanced_fixture
class BalancedGateTests(unittest.TestCase):
 def fixture(self):
  frames=[{'identity':f's{i}:100','positive_anchors':{str(c):1 for c in range(1,5)}} for i in range(16)]
  audited=[{'identity':f's{i}:100','covered_objects':{str(c):[f'obj{i}'] for c in range(1,5)},'positive_anchor_counts_by_class':{str(c):1 for c in range(1,5)},'all_anchor_labels_indices_residuals_directions_exact':True} for i in range(16)]
  claim={str(c):{'eligible_objects':16,'unique_tracks':16,'frames':16,'scenes':16} for c in range(1,5)}
  return frames,{'frames':frames},{'validation':audited,'positive_anchor_covered_object_coverage':claim,'label_and_anchor_coverage_gate_passed':True}
 def test_stale_progress_rejected(self):
  frames,selection,audit=self.fixture();frames=[dict(f) for f in frames];frames[0]['identity']='stale:100'
  with self.assertRaises(ValueError):validate_balanced_fixture(frames,selection,audit)
 def test_unlinked_anchor_counts_rejected(self):
  frames,selection,audit=self.fixture();frames[0]['positive_anchors']={'1':99,'2':1,'3':1,'4':1}
  with self.assertRaises(ValueError):validate_balanced_fixture(frames,selection,audit)
 def test_exact_independent_selection_passes(self):
  self.assertEqual(validate_balanced_fixture(*self.fixture())['frames'],16)
