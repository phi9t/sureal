import unittest
import numpy as np
from pipeline.pillar_packing import pack_points


class PillarPackingTests(unittest.TestCase):
    def test_half_open_roi_metric_cells_and_source_identity(self):
        points=np.array([[-1.,-1.,0.,.1],[-.5,-.5,.1,.2],[0.,0.,0.,.3],
                         [1.,0.,0.,.4],[0.,0.,1.,.5],[-1.01,0.,0.,.6]])
        result=pack_points(points,roi=(-1.,-1.,-1.,1.,1.,1.),cell_size=(1.,1.),max_pillars=10,max_points=3,seed=17)
        np.testing.assert_array_equal(result['coordinates'],[[0,0,0,0],[0,0,1,1]])
        np.testing.assert_array_equal(result['counts'],[2,1])
        np.testing.assert_array_equal(result['source_indices'],[[0,1,-1],[2,-1,-1]])
        np.testing.assert_array_equal(result['points'][0,:2],points[:2])
        self.assertEqual(result['counts_report']['outside_roi'],3)

    def test_caps_repeat_and_reconcile_all_exclusions(self):
        points=np.array([[x+.1,0.,0.,float(i)] for x in range(4) for i in range(5)])
        params=dict(roi=(0.,-1.,-1.,4.,1.,1.),cell_size=(1.,1.),max_pillars=2,max_points=3,seed=17)
        first=pack_points(points,**params);second=pack_points(points,**params)
        np.testing.assert_array_equal(first['source_indices'],second['source_indices'])
        report=first['counts_report'];self.assertEqual(report['pillar_limit_dropped_points'],10)
        self.assertEqual(report['point_limit_dropped_points'],4);self.assertEqual(report['retained_points'],6)
        valid=first['source_indices'][first['source_indices']>=0]
        self.assertEqual(len(np.unique(valid)),6)
        np.testing.assert_array_equal(first['points'][first['source_indices']>=0],points[valid])

    def test_empty_and_nonphysical_inputs(self):
        params=dict(roi=(-1.,-1.,-1.,1.,1.,1.),cell_size=(1.,1.),max_pillars=2,max_points=3,seed=17)
        result=pack_points(np.empty((0,4)),**params);self.assertEqual(result['points'].shape,(0,3,4))
        for points in [np.ones((2,5)),np.array([[float('nan'),0.,0.,1.]])]:
            with self.assertRaises(ValueError):pack_points(points,**params)


if __name__=='__main__':unittest.main()
