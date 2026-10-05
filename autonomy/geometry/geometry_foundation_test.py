"""Independent analytic fixtures for the project geometry convention."""
import unittest
import numpy as np
from geometry.geometry_foundation import (
    skew, so3_exp, so3_log, se3_exp, se3_log, inverse, transform,
    adjoint, point_jacobian, polar_to_cartesian, cartesian_to_polar,
    polar_jacobian, bev_indices, pinhole_project, radar_radial_velocity)


class GeometryFoundationTests(unittest.TestCase):
    def test_noncommuting_transform_and_inverse(self):
        rotation = np.eye(4)
        rotation[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
        translation = np.eye(4)
        translation[:3, 3] = [2, 0, 0]
        np.testing.assert_allclose(transform(rotation @ translation, [1, 0, 0]), [0, 3, 0])
        np.testing.assert_allclose(transform(translation @ rotation, [1, 0, 0]), [2, 1, 0])
        np.testing.assert_allclose(inverse(rotation @ translation) @ rotation @ translation, np.eye(4))

    def test_coupled_se3_exponential(self):
        pose = se3_exp([0, 0, np.pi/2, 1, 0, 0])
        np.testing.assert_allclose(pose[:3, 3], [2/np.pi, 2/np.pi, 0], atol=1e-12)
        self.assertFalse(np.allclose(pose[:3, 3], [1, 0, 0]))
        for xi in [[0]*6, [1e-9, -2e-9, 3e-9, 2, -1, 3], [.2, -.3, .4, 2, 1, -3]]:
            np.testing.assert_allclose(se3_log(se3_exp(xi)), xi, atol=1e-8)

    def test_rotation_log_near_pi(self):
        for axis in np.eye(3):
            rotation = so3_exp(axis * (np.pi-1e-9))
            np.testing.assert_allclose(so3_exp(so3_log(rotation)), rotation, atol=1e-7)
        with self.assertRaises(ValueError):
            so3_log(np.diag([2, 1, 1]))

    def test_right_perturbation_jacobian_and_adjoint(self):
        pose = se3_exp([.2, -.1, .3, 2, 1, -1])
        point = np.array([3., -2., 1.])
        expected = point_jacobian(pose, point)
        for step in [1e-5, 1e-6]:
            columns = []
            for i in range(6):
                delta = np.eye(6)[i]*step
                columns.append((transform(pose @ se3_exp(delta), point)-transform(pose @ se3_exp(-delta), point))/(2*step))
            np.testing.assert_allclose(np.array(columns).T, expected, atol=1e-8)
        xi = np.array([.01, -.02, .03, .04, -.02, .01])
        np.testing.assert_allclose(pose @ se3_exp(xi) @ inverse(pose), se3_exp(adjoint(pose) @ xi), atol=1e-12)

    def test_polar_axes_singularities_and_jacobian(self):
        np.testing.assert_allclose(polar_to_cartesian([[2, 0, 0], [2, np.pi/2, 0], [2, 0, np.pi/2]]), [[2,0,0],[0,2,0],[0,0,2]], atol=1e-12)
        polar, valid = cartesian_to_polar([[0,0,0],[0,0,2],[2,0,0]])
        self.assertEqual(valid.tolist(), [False,False,True])
        self.assertTrue(np.isnan(polar[0,1:]).all())
        sample = np.array([3., .4, -.2])
        h=1e-6
        numeric=np.column_stack([(polar_to_cartesian(sample+np.eye(3)[i]*h)-polar_to_cartesian(sample-np.eye(3)[i]*h))/(2*h) for i in range(3)])
        np.testing.assert_allclose(polar_jacobian(sample), numeric, atol=1e-9)

    def test_bev_half_open_edges_and_projection(self):
        cells, valid = bev_indices([[-1,-1], [0,0], [1,1], [-1.001,0]], [-1,-1], [1,1], [.5,.5])
        self.assertEqual(valid.tolist(), [True,True,False,False])
        self.assertEqual(cells[:2].tolist(), [[0,0],[2,2]])
        uv, valid=pinhole_project([[1,2,4],[1,2,0],[1,2,-1]], [100,200,20,30])
        np.testing.assert_allclose(uv[0], [45,130])
        self.assertEqual(valid.tolist(),[True,False,False])
        self.assertTrue(np.isnan(uv[1:]).all())

    def test_radar_is_relative_radial_velocity(self):
        self.assertAlmostEqual(radar_radial_velocity([10,0,0], [3,5,0], [1,0,0]), 2)
        with self.assertRaises(ValueError):
            radar_radial_velocity([0,0,0], [3,5,0], [1,0,0])

    def test_covariance_transport_and_sensor_time_chain(self):
        from geometry.geometry_foundation import transport_covariance, sensor_to_reference
        covariance=np.diag([.01,.02,.03,.04,.05,.06])
        jacobian=np.array([[1,2,0,0,0,0],[0,0,3,0,0,0]])
        np.testing.assert_allclose(transport_covariance(jacobian,covariance), [[.09,0],[0,.27]])
        rng=np.random.default_rng(7)
        noise=rng.multivariate_normal(np.zeros(6),covariance,size=100000)
        np.testing.assert_allclose(np.cov((noise @ jacobian.T).T), transport_covariance(jacobian,covariance),atol=.003)
        bad=covariance.copy();bad[0,0]=-1
        with self.assertRaises(ValueError): transport_covariance(jacobian,bad)
        world_reference=np.eye(4);world_reference[:3,3]=[10,0,0]
        world_acquisition=np.eye(4);world_acquisition[:3,3]=[12,0,0]
        vehicle_sensor=np.eye(4);vehicle_sensor[:3,3]=[0,1,0]
        np.testing.assert_allclose(sensor_to_reference([[2,0,0]],vehicle_sensor,world_acquisition,world_reference),[[4,1,0]])

    def test_bev_nextafter_upper_edge_stays_inside_last_cell(self):
        point=np.nextafter(1.,-np.inf)
        cells,valid=bev_indices([[point,point]],[-1,-1],[1,1],[.5,.5])
        self.assertTrue(valid[0])
        self.assertEqual(cells.tolist(),[[3,3]])

    def test_negative_covariance_cannot_be_amplified(self):
        from geometry.geometry_foundation import transport_covariance
        with self.assertRaises(ValueError):
            transport_covariance([[1e8]],[[-1e-13]])

    def test_nonfinite_inputs_fail(self):
        for operation in [lambda: so3_exp([np.nan,0,0]), lambda: se3_exp([0]*5),
                          lambda: polar_to_cartesian([-1,0,0]),
                          lambda: bev_indices([[0,0]], [0,0],[1,1],[0,1])]:
            with self.assertRaises(ValueError): operation()
