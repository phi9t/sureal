import copy,unittest
from cohort.sustained_groundtruth import groundtruth_records
class FullGroundtruthTests(unittest.TestCase):
 def rows(self):
  return [{'object_id':str(i),'type':cls,'box':box,'num_lidar_points_in_box':points,'detection_difficulty':0} for i,(cls,box,points) in enumerate([(1,[0.,0.,0.,4.,2.,1.,0.],10),(2,[70.,0.,0.,1.,1.,2.,7.],6),(3,[0.,0.,0.,1.,1.,1.,0.],0),(4,[0.,0.,7.,2.,1.,1.,0.],2)])]
 def test_outside_roi_zero_points_and_uncovered_native_boxes_retained(self):
  records,training=groundtruth_records(self.rows(),'scene',123)
  self.assertEqual(len(records),4);self.assertEqual(training,['0']);self.assertEqual([r['object_id'] for r in records],['0','1','2','3']);self.assertEqual(records[2]['num_lidar_points_in_box'],0);self.assertTrue(-3.142<=records[1]['box'][6]<3.142)
 def test_bad_native_geometry_identity_and_counts_refused(self):
  for field,value in [('box',[0.,0.,0.,0.,1.,1.,0.]),('box',[float('nan'),0.,0.,1.,1.,1.,0.]),('num_lidar_points_in_box',-1),('type',5),('object_id','')]:
   rows=self.rows();rows[0][field]=value
   with self.assertRaises(ValueError):groundtruth_records(rows,'scene',123)
  rows=self.rows();rows[1]['object_id']=rows[0]['object_id']
  with self.assertRaises(ValueError):groundtruth_records(rows,'scene',123)
 def test_unspecified_native_difficulty_is_preserved(self):
  rows=self.rows();rows[0]['detection_difficulty']=None;records,_=groundtruth_records(rows,'scene',123);self.assertIsNone(records[0]['difficulty'])
 def test_source_rows_unchanged(self):
  rows=self.rows();before=copy.deepcopy(rows);groundtruth_records(rows,'scene',123);self.assertEqual(rows,before)
if __name__=='__main__':unittest.main()
