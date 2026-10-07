import hashlib,json
from pathlib import Path
import tempfile,unittest
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from dataset.scientific_sidecars import materialize_component
from geometry.scientific_reconstruction import reconstruct_scene

class ScientificReconstructionTests(unittest.TestCase):
    def fixture(self,root,*,missing_pose=False,missing_sensor=False,missing_return=False):
        def key(laser=None):
            d={'key.segment_context_name':'scene','key.frame_timestamp_micros':10}
            if laser is not None:d['key.laser_name']=laser
            return d
        def shaped(d,prefix,values,shape):d[prefix+'.values']=values;d[prefix+'.shape']=shape;return d
        components={}
        p='[LiDARCalibrationComponent]'
        components['lidar_calibration']=[{'key.segment_context_name':'scene','key.laser_name':laser,p+'.extrinsic.transform':np.eye(4).ravel().tolist(),p+'.beam_inclination.values':[0.],p+'.beam_inclination.min':0.,p+'.beam_inclination.max':0.} for laser in range(1,6)]
        frame=np.eye(4);frame[0,3]=3
        components['vehicle_pose']=[{**key(),'[VehiclePoseComponent].world_from_vehicle.transform':frame.ravel().tolist()}]
        poses=np.zeros((1,2,6));poses[...,3]=7
        components['lidar_pose']=[shaped(key(1),'[LiDARPoseComponent].range_image_return1',poses.ravel().tolist(),[1,2,6])]
        components['lidar_camera_projection']=[]
        for laser in range(1,6):
            d=key(laser)
            for ret in (1,2):shaped(d,f'[LiDARCameraProjectionComponent].range_image_return{ret}',list(range(12)),[1,2,6])
            components['lidar_camera_projection'].append(d)
        d=key(1)
        for ret in (1,2):shaped(d,f'[LiDARSegmentationLabelComponent].range_image_return{ret}',[99,1,88,2],[1,2,2])
        components['lidar_segmentation']=[d]
        sidecars=root/'sidecars';sidecars.mkdir();hashes={}
        for c,rows in components.items():
            table=pa.Table.from_pylist(rows)
            if c=='lidar_pose' and missing_pose:table=table.slice(0,0)
            source=root/(c+'.parquet');pq.write_table(table,source)
            materialize_component(source,c,'scene',sidecars/c,10**7)
            hashes[c]=hashlib.sha256((sidecars/c/'manifest.json').read_bytes()).hexdigest()
        rows=[]
        for laser in range(1,5 if missing_sensor else 6):
            d=key(laser)
            for ret in (1,2):
                missing=missing_return and laser==1 and ret==2
                shaped(d,f'[LiDARComponent].range_image_return{ret}',None if missing else [1.,2.,3.,-1.,0.,4.,5.,1.],None if missing else [1,2,4])
            rows.append(d)
        source=root/'lidar.parquet';pq.write_table(pa.Table.from_pylist(rows),source)
        return source,sidecars,hashes

    def test_both_returns_motion_reference_and_target_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,sidecars,hashes=self.fixture(root);out=root/'points'
            report=reconstruct_scene(source,sidecars,out,10**7,verified_manifest_hashes=hashes)
            self.assertEqual(len(report['rows']),10);self.assertEqual(report['points'],10)
            for row in report['rows']:
                with np.load(out/row['artifact'],allow_pickle=False) as a:
                    np.testing.assert_array_equal(a['pixels'],[[0,0]])
                    np.testing.assert_array_equal(a['physical_features'],[[1,2,3]])
                    self.assertEqual(a['nlz'].tolist(),[-1])
                    np.testing.assert_allclose(a['xyz'],[[4 if row['laser']==1 else 0,1,0]],atol=1e-12)
                    if row['laser']==1:np.testing.assert_array_equal(a['segmentation'],[[99,1]])
                    else:self.assertNotIn('segmentation',a.files)
            self.assertLessEqual(report['working_set_bytes'],10**7)

    def test_missing_return_recorded_separately_from_zero_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s,d,h=self.fixture(root,missing_return=True)
            r=reconstruct_scene(s,d,root/'points',10**7,verified_manifest_hashes=h)
            missing=[x for x in r['rows'] if not x['return_present']]
            self.assertEqual(len(missing),1);self.assertIsNone(missing[0]['artifact']);self.assertEqual(r['points'],9)

    def test_missing_top_pose_sensor_and_budget_rejected(self):
        for kwargs in ({'missing_pose':True},{'missing_sensor':True},{}):
            with self.subTest(kwargs=kwargs),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);s,d,h=self.fixture(root,**kwargs);out=root/'points'
                with self.assertRaises(ValueError):reconstruct_scene(s,d,out,1 if not kwargs else 10**7,verified_manifest_hashes=h)
                self.assertFalse((out/'report.json').exists())

if __name__=='__main__':unittest.main()
