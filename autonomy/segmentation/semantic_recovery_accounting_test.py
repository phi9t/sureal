import copy,json,unittest
from pathlib import Path
from segmentation.semantic_recovery_accounting import verify_accounting
class AccountingTests(unittest.TestCase):
 def test_real_fixture(self):
  r=json.loads(Path('/source/receipt.json').read_text())
  verify_accounting(r['validation'],r['input_identity'])
 def test_mutated_accounting(self):
  r=json.loads(Path('/source/receipt.json').read_text()); v=r['validation']; d=r['input_identity']
  changes=[lambda x:x.update(eligible_point_elements=0),lambda x:x.update(labeled_point_elements=0),lambda x:x.update(unannotated_returns=7),lambda x:x.update(annotated_frames=2),lambda x:x.update(frame_counts=[]),lambda x:x['native_counts'].__setitem__(14,-1),lambda x:x.update(membership={'official_split':'validation','research_splits':['train']}),lambda x:x.update(archive_sha256='0'*64),lambda x:x.update(scene='other'),lambda x:x.update(independent_reference_records=9),lambda x:x['worker_resources'].update(peak_rss_kib=0)]
  for change in changes:
   with self.subTest(change=change):
    m=copy.deepcopy(v);change(m)
    with self.assertRaises(ValueError):verify_accounting(m,d)
if __name__=='__main__':unittest.main()
