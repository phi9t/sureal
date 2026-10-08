import unittest
import numpy as np
from dataset.sensor_records import array_field, align_point_targets

class SensorRecordTests(unittest.TestCase):
    def test_shape_and_nullable_payload(self):
        row={'x.values':[1,2,3,4],'x.shape':[2,2]}
        np.testing.assert_array_equal(array_field(row,'x'),[[1,2],[3,4]])
        self.assertIsNone(array_field({'x.values':None,'x.shape':None},'x'))
        with self.assertRaises(ValueError):array_field({'x.values':[1],'x.shape':[2,2]},'x')

    def test_projection_semantic_identity_and_missing(self):
        pixels=np.array([[1,0],[0,1]])
        projections=np.arange(24).reshape(2,2,6)
        segmentation=np.arange(8).reshape(2,2,2)
        result=align_point_targets(pixels,(2,2),projections,segmentation)
        np.testing.assert_array_equal(result['camera_projection'],[[12,13,14,15,16,17],[6,7,8,9,10,11]])
        np.testing.assert_array_equal(result['segmentation'],[[4,5],[2,3]])
        self.assertIsNone(align_point_targets(pixels,(2,2),projections,None)['segmentation'])
        with self.assertRaises(ValueError):align_point_targets(pixels,(2,2),projections[:1],segmentation)
        with self.assertRaises(ValueError):align_point_targets(np.array([[2,0]]),(2,2),projections,segmentation)

class OrderedLookupTests(unittest.TestCase):
    def test_sparse_reuse_missing_and_backward_rejected(self):
        from dataset.sensor_records import OrderedLookup
        lookup=OrderedLookup(iter([{'key.frame_timestamp_micros':2,'key.laser_name':1,'v':7}, {'key.frame_timestamp_micros':4,'key.laser_name':1,'v':9}]))
        self.assertIsNone(lookup.get((1,1)))
        self.assertEqual(lookup.get((2,1))['v'],7)
        self.assertEqual(lookup.get((2,1))['v'],7)
        self.assertIsNone(lookup.get((3,1)))
        self.assertEqual(lookup.get((4,1))['v'],9)
        with self.assertRaises(ValueError):lookup.get((2,1))

if __name__ == '__main__':
    unittest.main()
