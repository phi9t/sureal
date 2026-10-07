import unittest
import numpy as np
from detection.scored_proposals_v3 import canonical_direction_correct
class DirectionTests(unittest.TestCase):
 def test_turn_invariance(self):
  yaw=np.array([-3.,-1.,.5,2.7]);bins=np.array([0,0,1,1])
  for turns in [-4,-2,-1,0,1,2,4]:np.testing.assert_allclose(canonical_direction_correct(yaw+turns*2*np.pi,bins),yaw,rtol=0,atol=2e-14)
 def test_sine_ambiguous_branch(self):
  yaw=np.array([-3.,-1.,.5,2.7]);bins=np.array([0,0,1,1])
  for shift in [-3*np.pi,-np.pi,np.pi,3*np.pi]:np.testing.assert_allclose(canonical_direction_correct(yaw+shift,bins),yaw,rtol=0,atol=2e-14)
 def test_invalid_bins(self):
  with self.assertRaises(ValueError):canonical_direction_correct(np.array([.5]),np.array([2]))

if __name__ == '__main__':
 unittest.main()
