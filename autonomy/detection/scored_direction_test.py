import math
import unittest
import numpy as np
from detection.box_coding import direction_correct
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
 def test_raw_and_canonical_direction_rules_differ_outside_half_open_range(self):
  inside=np.array([-math.pi,-math.pi,0.,0.,.25])
  bins=np.array([0,1,0,1,1])
  np.testing.assert_allclose(direction_correct(inside,bins),canonical_direction_correct(inside,bins),rtol=0,atol=0)

  outside=np.array([math.pi,math.pi,math.pi+.25,-math.pi-.25])
  outside_bins=np.array([0,1,0,1])
  raw_rule=direction_correct(outside,outside_bins)
  canonical_rule=canonical_direction_correct(outside,outside_bins)
  np.testing.assert_allclose(raw_rule,np.array([0.,-math.pi,.25,-.25]),rtol=0,atol=1e-15)
  np.testing.assert_allclose(canonical_rule,np.array([-math.pi,0.,-math.pi+.25,math.pi-.25]),rtol=0,atol=1e-15)
  self.assertFalse(np.any(raw_rule==canonical_rule))

if __name__ == '__main__':
 unittest.main()
