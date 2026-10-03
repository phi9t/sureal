"""Native protobuf causal boundary fixtures, separate from candidate process."""
import subprocess,tempfile,unittest
from pathlib import Path
BINARY='/outputs/motion_causal_project'
PROTO=['protoc','--proto_path=/upstream/src','waymo_open_dataset/protos/scenario.proto']
class CausalTests(unittest.TestCase):
 def source(self):
  return 'scenario_id: "causal" current_time_index: 1 sdc_track_index: 0 timestamps_seconds: 0 timestamps_seconds: .1 timestamps_seconds: .2 tracks { id: 7 object_type: TYPE_VEHICLE states { center_x: 1 valid: true } states { center_x: 2 valid: true } states { center_x: 999 valid: true } } dynamic_map_states {} dynamic_map_states {} dynamic_map_states { lane_states { lane: 999 } } tracks_to_predict { track_index: 0 } objects_of_interest: 7'
 def run_projection(self,text):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'truth.bin';out=root/'input.bin'
   encoded=subprocess.run(PROTO+['--encode=waymo.open_dataset.Scenario'],input=text.encode(),capture_output=True);self.assertEqual(encoded.returncode,0,encoded.stderr);source.write_bytes(encoded.stdout)
   r=subprocess.run([BINARY,str(source),str(out)],capture_output=True,text=True)
   self.assertEqual(source.read_bytes(),encoded.stdout)
   if r.returncode:return r,None,out.exists()
   decoded=subprocess.run(PROTO+['--decode=waymo.open_dataset.Scenario'],input=out.read_bytes(),capture_output=True);self.assertEqual(decoded.returncode,0,decoded.stderr)
   return r,decoded.stdout.decode(),out.exists()
 def test_actual_proto_future_truth_excluded(self):
  r,text,_=self.run_projection(self.source());self.assertEqual(r.returncode,0,r.stderr)
  self.assertEqual(text.count('timestamps_seconds:'),2);self.assertEqual(text.count('\n  states {'),2)
  self.assertNotIn('999',text);self.assertNotIn('tracks_to_predict',text);self.assertNotIn('objects_of_interest',text)
  self.assertIn('id: 7',text);self.assertIn('center_x: 2',text)
 def test_future_sensor_rejected(self):
  for field in ['compressed_frame_laser_data','frame_camera_tokens']:
   r,_,exists=self.run_projection(self.source()+' '+(field+' {} ')*3);self.assertNotEqual(r.returncode,0);self.assertFalse(exists)
 def test_native_timeline_and_identity_rejected(self):
  for text in [self.source().replace('current_time_index: 1','current_time_index: 3'),self.source().replace('timestamps_seconds: .2','timestamps_seconds: .05'),self.source().replace('states { center_x: 999 valid: true }',''),self.source().replace('scenario_id: "causal"','scenario_id: ""')]:
   r,_,exists=self.run_projection(text);self.assertNotEqual(r.returncode,0);self.assertFalse(exists)
 def test_unknown_native_fields_rejected_recursively(self):
  def varint(x):
   out=bytearray()
   while x>127:out.append((x&127)|128);x>>=7
   out.append(x);return bytes(out)
  unknown=varint(100<<3)+varint(999)
  for nested in [False,True]:
   with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);encoded=subprocess.run(PROTO+['--encode=waymo.open_dataset.Scenario'],input=self.source().encode(),capture_output=True);self.assertEqual(encoded.returncode,0)
    data=encoded.stdout
    if nested:
     # Independently wrap an unknown state field in a known track/scenario.
     text='id: 8 object_type: TYPE_VEHICLE'
     track=subprocess.run(['protoc','--proto_path=/upstream/src','waymo_open_dataset/protos/scenario.proto','--encode=waymo.open_dataset.Track'],input=text.encode(),capture_output=True);self.assertEqual(track.returncode,0)
     payload=track.stdout+b''.join(varint((3<<3)|2)+varint(len(unknown))+unknown for _ in range(3))
     data+=varint((2<<3)|2)+varint(len(payload))+payload
    else:data+=unknown
    source=root/'truth.bin';source.write_bytes(data);out=root/'input.bin'
    r=subprocess.run([BINARY,str(source),str(out)],capture_output=True,text=True)
    self.assertNotEqual(r.returncode,0);self.assertFalse(out.exists())
 def test_current_sensor_counts_preserved(self):
  r,text,_=self.run_projection(self.source()+' compressed_frame_laser_data {} compressed_frame_laser_data {} frame_camera_tokens {} frame_camera_tokens {}');self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(text.count('compressed_frame_laser_data {'),2);self.assertEqual(text.count('frame_camera_tokens {'),2)
if __name__=='__main__':unittest.main()
