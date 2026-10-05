import unittest
from balanced import select_balanced,coverage_summary,uncovered_count
class BalancedTests(unittest.TestCase):
 def test_tracks_are_scene_namespaced(self):
  rows=[{'identity':f's{i}:1','objects':{'1':['same'],'2':[],'3':[],'4':[]}} for i in range(2)]
  self.assertEqual(coverage_summary(rows)['1']['unique_tracks'],2)
 def test_repeated_frames_do_not_fake_tracks(self):
  rows=[{'identity':f's:1{i}','objects':{str(c):['same'] for c in range(1,5)}} for i in range(16)]
  with self.assertRaises(ValueError):select_balanced(rows)
 def test_deterministic_full_coverage(self):
  rows=[{'identity':f's{i}:100','objects':{str(c):[f'obj{i}'] for c in range(1,5)}} for i in range(20)]
  a=select_balanced(rows);self.assertEqual(a,select_balanced(list(reversed(rows))));self.assertEqual(len(a),16)
  self.assertTrue(all(v['unique_tracks']>=8 for v in coverage_summary(a).values()))
 def test_four_frame_support_is_not_enough(self):
  rows=[]
  for i in range(20):
   rows.append({'identity':f's{i}:100','objects':{str(c):([f'obj{i}'] if c!=4 else [f'cyclist{i}-{j}' for j in range(4)] if i<4 else []) for c in range(1,5)}})
  with self.assertRaises(ValueError):select_balanced(rows)
 def test_exact_uncovered_schema(self):self.assertEqual(uncovered_count({'eligible_targets_without_positive_anchor':3,'uncovered_object_ids':['a','b','c']}),3)
 def test_uncovered_mismatch_refused(self):
  with self.assertRaises(ValueError):uncovered_count({'eligible_targets_without_positive_anchor':3,'uncovered_object_ids':[]})
if __name__=='__main__':unittest.main()
