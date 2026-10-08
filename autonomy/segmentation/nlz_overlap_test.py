import math,unittest
import numpy as np
from segmentation.nlz_overlap import overlaps_nlz

def returns():return {(laser,ret):(np.empty((0,3)),np.empty(0)) for laser in range(1,6) for ret in [1,2]}

class NLZTests(unittest.TestCase):
    def test_rotated_box_and_second_return_have_exact_overlap(self):
        data=returns();data[(5,2)]=(np.array([[10,1,0],[11.5,0,0]]),np.array([1,1]))
        self.assertTrue(overlaps_nlz([10,0,0,4,2,2,math.pi/2],data))
        data[(5,2)]=(np.array([[11.5,0,0]]),np.array([1]))
        self.assertFalse(overlaps_nlz([10,0,0,4,2,2,math.pi/2],data))

    def test_non_nlz_points_do_not_trigger_overlap(self):
        data=returns();data[(1,1)]=(np.array([[0,0,0]]),np.array([-1]))
        self.assertFalse(overlaps_nlz([0,0,0,2,2,2,0],data))

    def test_missing_return_and_unknown_flags_cannot_silently_be_false(self):
        data=returns();del data[(5,2)]
        with self.assertRaises(ValueError):overlaps_nlz([0,0,0,2,2,2,0],data)
        data=returns();data[(1,1)]=(np.array([[0,0,0]]),np.array([0]))
        with self.assertRaises(ValueError):overlaps_nlz([0,0,0,2,2,2,0],data)

if __name__=='__main__':unittest.main()
