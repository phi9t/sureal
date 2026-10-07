import unittest
import numpy as np
from inspection.inspection import bev_raster, projection_samples, range_raster

class InspectionTests(unittest.TestCase):
    def test_bev_half_open_and_display_axes(self):
        density,counts=bev_raster(np.array([[0,0,0],[1.9,1.9,0],[2,0,0],[-.1,0,0]]),lower=(0,0),upper=(2,2),cell=1)
        self.assertEqual(density.tolist(),[[0,1],[1,0]])
        self.assertEqual(counts,{'retained':2,'clipped':2})

    def test_projection_slots_preserve_point_identity(self):
        cp=np.array([[1,2,3,2,4,5],[2,-1,3,1,9,1],[1,10,1,0,0,0]])
        indexes,slots,uv=projection_samples(cp,1,10,8)
        self.assertEqual(indexes.tolist(),[0,1])
        self.assertEqual(slots.tolist(),[0,1])
        self.assertEqual(uv.tolist(),[[2,3],[9,1]])

    def test_range_unknown_and_pixels(self):
        image=range_raster(np.array([[0,1]]),np.array([5.]),(2,3))
        self.assertEqual(image[0,1],5)
        self.assertTrue(np.isnan(image[0,0]))
