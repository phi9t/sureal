import unittest
import numpy as np
from detection.anchor_grid import anchor_grid


class AnchorGridTests(unittest.TestCase):
    def test_metric_stride_two_row_column_anchor_order_and_center_z(self):
        result=anchor_grid(nx=4,ny=2,cell_size=(.5,1.),origin=(-1.,-1.),templates=np.array([[4.,2.,1.5,.7,0.],[1.,.5,2.,1.2,1.57]]))
        self.assertEqual(result.shape,(4,7))
        np.testing.assert_allclose(result,[[ -.5,0.,.7,4.,2.,1.5,0.],[-.5,0.,1.2,1.,.5,2.,1.57],
                                          [ .5,0.,.7,4.,2.,1.5,0.],[ .5,0.,1.2,1.,.5,2.,1.57]])

    def test_invalid_dimensions_and_metric_grid_refused(self):
        defaults=dict(nx=4,ny=2,cell_size=(.5,1.),origin=(-1.,-1.),templates=np.array([[4.,2.,1.5,.7,0.]]))
        for change in [{'nx':3},{'cell_size':(0.,1.)},{'templates':np.array([[0.,2.,1.5,.7,0.]])}]:
            with self.assertRaises(ValueError):anchor_grid(**(defaults|change))


if __name__=='__main__':unittest.main()
