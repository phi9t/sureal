import unittest
import numpy as np
from detection.prediction_records import prediction_records


class PredictionRecordTests(unittest.TestCase):
    def test_measured_point_metadata_and_generated_prediction_identity(self):
        returns={(laser,r):(np.empty((0,3)),np.empty(0)) for laser in range(1,6) for r in (1,2)}
        returns[1,1]=(np.array([[0.,0.,0.],[1.,0.,0.],[2.,0.,0.]]),np.array([-1,1,-1]))
        proposals={'boxes':np.array([[0.,0.,0.,2.,2.,2.,0.]]),'classes':np.array([1]),'scores':np.array([.8]),'anchor_indices':np.array([7])}
        records=prediction_records(proposals,context='scene',timestamp=10,sensor_returns=returns)
        self.assertEqual(records[0]['num_lidar_points_in_box'],2)
        self.assertTrue(records[0]['overlap_with_nlz'])
        self.assertEqual(records[0]['object_id'],'prediction-anchor-7')
        self.assertIsNone(records[0]['difficulty'])

    def test_missing_sensor_support_refused_even_when_no_predictions(self):
        proposals={'boxes':np.empty((0,7)),'classes':np.empty(0,dtype=np.int64),'scores':np.empty(0),'anchor_indices':np.empty(0,dtype=np.int64)}
        with self.assertRaises(ValueError):prediction_records(proposals,context='scene',timestamp=10,sensor_returns={})


if __name__=='__main__':unittest.main()
