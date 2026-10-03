import json,tempfile,unittest
from pathlib import Path
from admissions import validate_coverage_claim,required_fit_admissions
class AdmissionTests(unittest.TestCase):
 def test_inflated_coverage_is_rejected(self):
  frames=[{'identity':f's{i}:100','covered_objects':{str(c):[f'obj{i}'] for c in range(1,5)}} for i in range(16)]
  claim={str(c):{'eligible_objects':999,'unique_tracks':999,'frames':999,'scenes':999} for c in range(1,5)}
  with self.assertRaises(ValueError):validate_coverage_claim(claim,frames)
 def test_missing_class_is_rejected(self):
  with self.assertRaises(ValueError):validate_coverage_claim({'1':{}},[])
 def test_independent_ids_establish_coverage(self):
  frames=[{'identity':f's{i}:100','covered_objects':{str(c):[f'obj{i}'] for c in range(1,5)}} for i in range(16)]
  claim={str(c):{'eligible_objects':16,'unique_tracks':16,'frames':16,'scenes':16} for c in range(1,5)}
  self.assertEqual(validate_coverage_claim(claim,frames),claim)
 def test_fit_cannot_skip_replays(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):required_fit_admissions(Path(tmp))
if __name__=='__main__':unittest.main()
