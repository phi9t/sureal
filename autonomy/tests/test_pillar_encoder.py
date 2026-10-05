"""Analytic checks of source-compatible decorations and metric XY scatter."""
import unittest
import torch
from pipeline.pillar_encoder import decorate, PillarFeatureNet, scatter


class PillarEncoderTests(unittest.TestCase):
    def inputs(self):
        return (torch.tensor([[[1., 2., 3., 4.], [3., 4., 5., 6.],
                              [99., 99., 99., 99.]]]),
                torch.tensor([2]), torch.tensor([[0, 0, 1, 2]]))

    def test_exact_decorations_and_padding(self):
        points, counts, coordinates = self.inputs()
        actual = decorate(points, counts, coordinates, cell_size=(2., 2.), origin=(0., 0.))
        expected = torch.tensor([[[1.,2.,3.,4.,-1.,-1.,-1.,-4.,-1.],
                                  [3.,4.,5.,6.,1.,1.,1.,-2.,1.],
                                  [0.,0.,0.,0.,0.,0.,0.,0.,0.]]])
        torch.testing.assert_close(actual, expected)

    def test_singleton_permutation_and_finite_gradients(self):
        points, counts, coordinates = self.inputs()
        model = PillarFeatureNet().eval()
        features = decorate(points, counts, coordinates, cell_size=(2.,2.), origin=(0.,0.))
        features.requires_grad_()
        result = model(features)
        self.assertEqual(tuple(result.shape), (1,64))
        torch.testing.assert_close(result, model(features[:,[1,0,2]]))
        result.sum().backward()
        self.assertTrue(torch.isfinite(features.grad).all())
        self.assertEqual(tuple(model(features[:,:1]).shape), (1,64))

    def test_scatter_xy_orientation_empty_cells_and_duplicates(self):
        features = torch.tensor([[7.,8.],[9.,10.]])
        coordinates = torch.tensor([[0,0,1,2],[1,0,0,1]])
        actual = scatter(features, coordinates, batch_size=2, nx=3, ny=2)
        self.assertEqual(tuple(actual.shape),(2,2,2,3))
        torch.testing.assert_close(actual[0,:,1,2],features[0])
        torch.testing.assert_close(actual[1,:,0,1],features[1])
        self.assertEqual(float(actual[0,:,0,0].sum()),0.)
        with self.assertRaises(ValueError):
            scatter(features,coordinates[[0,0]],batch_size=2,nx=3,ny=2)

    def test_invalid_count_and_nonfinite_observation_refused(self):
        for kind in ['zero','too_many','nan']:
            points,counts,coordinates = self.inputs()
            if kind=='zero':counts[0]=0
            elif kind=='too_many':counts[0]=4
            else:points[0,0,0]=float('nan')
            with self.assertRaises(ValueError):
                decorate(points,counts,coordinates,cell_size=(2.,2.),origin=(0.,0.))


if __name__=='__main__':
    unittest.main()
