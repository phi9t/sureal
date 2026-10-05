import copy,unittest
from pipeline.detection_export import validate_object

VALID={'context_name':'scene','frame_timestamp_micros':10,'object_id':'object','type':1,'box':[1.,2.,3.,4.,2.,1.,0.],'score':0.8,'overlap_with_nlz':False,'num_lidar_points_in_box':20,'difficulty':None}

class DetectionExportTests(unittest.TestCase):
    def test_valid_box_preserves_native_dimension_order(self):
        self.assertEqual(validate_object(VALID),VALID)

    def test_invalid_geometry_labels_scores_and_unknown_nlz_fail(self):
        changes=[('box',[1,2,3,0,2,1,0]),('box',[float('nan'),2,3,4,2,1,0]),('score',1.1),('type',8),('overlap_with_nlz',None),('num_lidar_points_in_box',-1),('difficulty',9),('difficulty',1.0),('frame_timestamp_micros',True)]
        for key,value in changes:
            item=copy.deepcopy(VALID);item[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_object(item)

if __name__=='__main__':unittest.main()
