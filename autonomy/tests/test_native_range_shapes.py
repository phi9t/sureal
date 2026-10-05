import copy,hashlib,json,unittest
from pipeline.native_range_shapes import native_range_shapes
class ShapeTests(unittest.TestCase):
 def rows(self):
  return [{'key.segment_context_name':'scene','key.frame_timestamp_micros':10,'key.laser_name':1,'[LiDARComponent].range_image_return1.shape':[64,2650,4],'[LiDARComponent].range_image_return2.shape':None},{'key.segment_context_name':'scene','key.frame_timestamp_micros':10,'key.laser_name':2,'[LiDARComponent].range_image_return1.shape':[8,100,4],'[LiDARComponent].range_image_return2.shape':[8,100,4]}]
 def expected(self,rows):
  h=hashlib.sha256()
  for r in rows:h.update((json.dumps({k:r[k] for k in r if k.startswith('key.')},sort_keys=True,separators=(',',':'))+'\n').encode())
  return {'rows':len(rows),'key_sha256':h.hexdigest()}
 def test_native_dimensions_and_missing_return_preserved(self):
  rows=self.rows();r=native_range_shapes(iter(rows),scene='scene',inventory=self.expected(rows));self.assertEqual(len(r['records']),4);self.assertIsNone(r['records'][1]['native_shape']);self.assertEqual(r['present_shape_records'],3);self.assertEqual(r['null_shape_records'],1);self.assertEqual(r['records'][0]['native_shape'],[64,2650,4]);self.assertEqual(rows,self.rows())
 def test_invalid_rows_and_shapes_refused(self):
  for field,value in [('key.segment_context_name','other'),('key.frame_timestamp_micros',True),('key.laser_name',6),('[LiDARComponent].range_image_return1.shape',[64,0,4]),('[LiDARComponent].range_image_return1.shape',[64,2650,3]),('[LiDARComponent].range_image_return1.shape',[64.,2650,4])]:
   rows=self.rows();expected=self.expected(rows);rows[0][field]=value
   with self.subTest(field=field,value=value),self.assertRaises(ValueError):native_range_shapes(rows,scene='scene',inventory=expected)
  rows=self.rows();expected=self.expected(rows)
  for actual in [rows[:1],rows+rows[:1],list(reversed(rows))]:
   with self.assertRaises(ValueError):native_range_shapes(actual,scene='scene',inventory=expected)
  rows=self.rows();del rows[0]['[LiDARComponent].range_image_return2.shape']
  with self.assertRaises(ValueError):native_range_shapes(rows,scene='scene',inventory=self.expected(rows))
if __name__=='__main__':unittest.main()
