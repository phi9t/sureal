import csv,subprocess,tempfile,unittest
from pathlib import Path
BINARY=Path('/outputs/build/project_camera')
IDENTITY=' '.join('transform: '+str(v) for v in [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1])
CALIB='name: FRONT intrinsic: 100 intrinsic: 100 intrinsic: 100 intrinsic: 50 '+ 'intrinsic: 0 '*5+'extrinsic { '+IDENTITY+' } width: 200 height: 100 rolling_shutter_direction: GLOBAL_SHUTTER'
IMAGE='name: FRONT pose { '+IDENTITY+' } velocity { v_x: 0 v_y: 0 v_z: 0 w_x: 0 w_y: 0 w_z: 0 } pose_timestamp: 0 shutter: 0 camera_trigger_time: 0 camera_readout_done_time: 0'
class ProjectionTests(unittest.TestCase):
 def invoke(self,folder,calibration=CALIB,image=IMAGE,points='10 0 0\n10 -1 -1\n-1 0 0\n'):
  root=Path(folder);(root/'calibration.txt').write_text(calibration);(root/'image.txt').write_text(image);(root/'points.txt').write_text(points)
  return subprocess.run([str(BINARY),str(root/'calibration.txt'),str(root/'image.txt'),str(root/'points.txt'),str(root/'projection.csv')],capture_output=True,text=True)
 def test_axis_depth_and_original_order(self):
  with tempfile.TemporaryDirectory() as root:
   result=self.invoke(root);self.assertEqual(result.returncode,0,result.stderr)
   with (Path(root)/'projection.csv').open() as file:rows=list(csv.reader(file))
   self.assertEqual(len(rows),3)
   self.assertEqual(list(map(float,rows[0])),[0,1,100,50,10]);self.assertEqual(list(map(float,rows[1])),[1,1,110,60,10]);self.assertEqual(rows[2][0:2],['2','0']);self.assertEqual(float(rows[2][4]),-1)
 def test_bad_metadata_and_truncated_points_refuse_output(self):
  variants=[{'calibration':CALIB.replace('intrinsic: 100','intrinsic: -100',1)},{'image':IMAGE.replace('name: FRONT','name: FRONT_LEFT')},{'points':'10 0\n'},{'calibration':CALIB+' unknown_field: 1'}]
  for variant in variants:
   with self.subTest(variant=variant),tempfile.TemporaryDirectory() as root:
    result=self.invoke(root,**variant);self.assertNotEqual(result.returncode,0);self.assertFalse((Path(root)/'projection.csv').exists())
if __name__=='__main__':unittest.main()
