import unittest,numpy as np
from geometry.native_range_grid import native_range_grid,gather_range_features
class GridTests(unittest.TestCase):
 def record(self):
  return {'identity':{'context':'scene','timestamp':1,'laser':1,'return':2,'pixels':np.array([[1,2],[0,0]])},'return_present':True,'observations':{'physical_features':np.array([[3.,.4,.5],[2.,.6,.7]]),'xyz':np.array([[1.,2.,3.],[4.,5.,6.]])},'targets':{'segmentation':np.array([[-1,14],[7,0]])},'evaluation':{'nlz':np.array([1,-1])}}
 def test_roundtrip_and_masks(self):
  r=self.record();g=native_range_grid(r,(3,5,4));self.assertEqual(g['measurements'].shape,(3,5,3));self.assertEqual(g['valid'].sum(),2)
  np.testing.assert_array_equal(gather_range_features(g,g['measurements']),r['observations']['physical_features'])
  self.assertTrue(g['semantic_supervised'][1,2]);self.assertFalse(g['semantic_supervised'][0,0]);self.assertEqual(g['source_indices'][1,2],0)
  self.assertEqual(g['source_indices'][2,4],-1);self.assertEqual(g['identity']['return'],2);self.assertNotIn('nlz',g)
 def test_missing_labels(self):
  r=self.record();r['targets']={};g=native_range_grid(r,(3,5,4));self.assertFalse(g['annotation_present']);self.assertFalse(g['semantic_supervised'].any());self.assertTrue((g['semantic_labels']==-1).all())
 def test_invalid_identity_refused(self):
  for pixels in [np.array([[0,0],[0,0]]),np.array([[3,0],[0,0]]),np.array([[1.,2.],[0.,0.]])]:
   r=self.record();r['identity']['pixels']=pixels
   with self.assertRaises(ValueError):native_range_grid(r,(3,5,4))
  with self.assertRaises(ValueError):native_range_grid(self.record(),(2,3))
if __name__=='__main__':unittest.main()
