import tempfile,unittest
from pathlib import Path
import numpy as np
import torch
from advanced.observations import load_observations
class ObservationTests(unittest.TestCase):
 def test_ragged_and_auxiliary_are_preserved_without_float_casting_ids(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'observations.npz'
   arrays={'points':np.ones((3,5),np.float64),'counts':np.array([2,1],np.int64),'coordinates':np.array([[0,0,2,1],[0,0,3,4]],np.int32),'range_pixels':np.array([[0,1,2]],np.int64),'range_valid_1_1':np.array([[[True]]])}
   np.savez(p,**arrays);obs,aux=load_observations(p,'cpu')
   self.assertEqual(obs[0].dtype,torch.float32)
   self.assertEqual(obs[1].dtype,torch.int64)
   self.assertEqual(obs[2].dtype,torch.int32)
   self.assertEqual(set(aux),{'range_pixels','range_valid_1_1'})
   np.testing.assert_array_equal(aux['range_pixels'].numpy(),arrays['range_pixels'])
   self.assertEqual(aux['range_valid_1_1'].dtype,torch.bool)
 def test_required_geometry_fields_are_enforced(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'observations.npz';np.savez(p,points=np.ones((2,4)))
   with self.assertRaises(KeyError):load_observations(p,'cpu')
if __name__=='__main__':unittest.main()
