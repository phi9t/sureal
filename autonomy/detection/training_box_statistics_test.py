"""Training-only native box statistic fixtures; no held-out parameter fitting."""
import unittest
from detection.training_box_statistics import training_box_statistics
class StatsTests(unittest.TestCase):
 def row(self,i,box=None,category=1):
  return {'context_name':'train-a','frame_timestamp_micros':i,'object_id':'track-a','type':category,'box':box or [0.,0.,1.,4.,2.,1.,0.]}
 def membership(self):return {'train-a':{'official_split':'training','research_splits':['train']}}
 def test_exact_native_class_statistics(self):
  rows=[self.row(1),self.row(2,[1.,2.,3.,8.,4.,3.,1.]),self.row(3,[1.,2.,5.,12.,6.,5.,2.]),self.row(4,category=2)]
  r=training_box_statistics(rows,membership=self.membership())
  self.assertEqual(r['classes']['1']['box_rows'],3);self.assertEqual(r['classes']['1']['unique_tracks'],1)
  self.assertEqual(r['classes']['1']['median_length_width_height_center_z'],[8.,4.,3.,3.])
  self.assertEqual(r['classes']['2']['box_rows'],1);self.assertEqual(r['classes']['3']['box_rows'],0)
  self.assertIsNone(r['classes']['3']['median_length_width_height_center_z']);self.assertEqual(r['frames'],4)
 def test_heldout_development_unknown_context_refused(self):
  for member in [{'official_split':'validation','research_splits':['validation']},{'official_split':'training','research_splits':['development']},{'official_split':'training','research_splits':['train','development']}]:
   with self.assertRaises(ValueError):training_box_statistics([self.row(1)],membership={'train-a':member})
  with self.assertRaises(ValueError):training_box_statistics([self.row(1)],membership={})
 def test_duplicate_and_bad_geometry_refused(self):
  with self.assertRaises(ValueError):training_box_statistics([self.row(1),self.row(1)],membership=self.membership())
  for b in [[0.,0.,0.,-1.,2.,1.,0.],[0.,0.,0.,4.,2.,1.,float('nan')]]:
   with self.assertRaises(ValueError):training_box_statistics([self.row(1,b)],membership=self.membership())
  with self.assertRaises(ValueError):training_box_statistics([self.row(1,category=0)],membership=self.membership())
 def test_empty_and_permutation(self):
  r=training_box_statistics([],membership=self.membership());self.assertEqual(r['rows'],0)
  rows=[self.row(1),self.row(2,[0.,0.,3.,8.,4.,3.,1.])]
  self.assertEqual(training_box_statistics(rows,membership=self.membership()),training_box_statistics(rows[::-1],membership=self.membership()))
if __name__=='__main__':unittest.main()
