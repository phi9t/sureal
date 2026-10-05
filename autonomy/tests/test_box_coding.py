"""Independent metric geometry fixtures for native center-Z box coding."""
import unittest
import math
import numpy as np
from pipeline.box_coding import encode_boxes, decode_boxes, direction_correct


class BoxCodingTests(unittest.TestCase):
    def test_analytic_translation_scale_and_center_z(self):
        anchor=np.array([[1.,2.,3.,4.,3.,2.,0.]])
        box=np.array([[6.,-3.,4.,8.,1.5,4.,math.pi/2]])
        expected=np.array([[1.,-1.,.5,math.log(2),math.log(.5),math.log(2),math.pi/2]])
        np.testing.assert_allclose(encode_boxes(box,anchor),expected,atol=1e-12)
        np.testing.assert_allclose(decode_boxes(expected,anchor),box,atol=1e-12)

    def test_wrap_equivalent_rotations_and_empty_catalog(self):
        anchor=np.array([[0.,0.,2.,4.,2.,2.,math.pi-.1]])
        box=anchor.copy();box[:,6]=-math.pi+.1
        residual=encode_boxes(box,anchor)
        self.assertAlmostEqual(residual[0,6],-2*math.pi+.2)
        np.testing.assert_allclose(decode_boxes(residual,anchor),box,atol=1e-12)
        for function in [encode_boxes,decode_boxes]:
            self.assertEqual(function(np.empty((0,7)),np.empty((0,7))).shape,(0,7))

    def test_direction_bin_corrects_pi_ambiguity(self):
        yaw=np.array([.2,-.2,.2,-.2])
        result=direction_correct(yaw,np.array([1,0,0,1]))
        np.testing.assert_allclose(result,[.2,-.2,.2-math.pi,math.pi-.2],atol=1e-12)

    def test_invalid_shapes_dimensions_and_overflow_refused(self):
        anchor=np.array([[0.,0.,0.,4.,2.,2.,0.]])
        for kind in ['shape','dimension','nan','overflow']:
            with self.subTest(kind=kind):
                if kind=='shape':
                    with self.assertRaises(ValueError):encode_boxes(anchor[:,:6],anchor)
                elif kind=='overflow':
                    residual=np.zeros((1,7));residual[0,3]=1000
                    with self.assertRaises(ValueError):decode_boxes(residual,anchor)
                else:
                    box=anchor.copy();box[0,3]=0 if kind=='dimension' else float('nan')
                    with self.assertRaises(ValueError):encode_boxes(box,anchor)


if __name__=='__main__':unittest.main()
