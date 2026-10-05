import hashlib,json,tempfile,unittest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from pipeline.camera_sidecars import materialize_camera_component
from dataset.component_archive import create_component_archive
from pipeline.camera_dataset import iter_camera_records
class CameraDatasetTests(unittest.TestCase):
 def fixture(self,root):
  source=root/'source';source.mkdir();scene='scene'
  for component in ['camera_image','camera_segmentation','camera_box']:
   fields={'key.segment_context_name':['scene'],'key.frame_timestamp_micros':[10],'key.camera_name':[1]}
   if component=='camera_image':fields['image']=pa.array([b'jpeg'],type=pa.binary())
   elif component=='camera_segmentation':fields['label']=pa.array([b'png'],type=pa.binary());fields['divisor']=[1000]
   else:fields['key.camera_object_id']=['object'];fields['type']=[2]
   p=root/(component+'.parquet');pq.write_table(pa.table(fields),p);materialize_camera_component(p,component,scene,source/component,100000)
  files={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()};archive=root/'camera.tar';meta=create_component_archive(source,archive,expected_files=files,provenance={'scene':scene},other_bytes=0,budget_bytes=1000000)
  pub=root/'publication.json';pub.write_text(json.dumps({'schema_version':1,'role':'scientific-native-camera-components','scene':scene,'official_split':'training','research_splits':['train'],'archive':meta,'provenance':{'scene':scene}}));return archive,pub,hashlib.sha256(pub.read_bytes()).hexdigest()
 def test_original_bytes_keys_and_observation_target_separation(self):
  with tempfile.TemporaryDirectory() as tmp:
   a,p,h=self.fixture(Path(tmp));records=list(iter_camera_records(a,p,expected_publication_sha256=h,usage='train'));self.assertEqual(len(records),3)
   image=next(r for r in records if r['component']=='camera_image');self.assertEqual(image['observations']['image'],b'jpeg');self.assertEqual(image['targets'],{});self.assertEqual(image['identity']['key.camera_name'],1)
   target=next(r for r in records if r['component']=='camera_segmentation');self.assertEqual(target['observations'],{});self.assertEqual(target['targets']['label'],b'png')
 def test_wrong_publication_split_and_resident_cap_rejected(self):
  for kind in ['hash','split','cap']:
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
    a,p,h=self.fixture(Path(tmp))
    with self.assertRaises(ValueError):list(iter_camera_records(a,p,expected_publication_sha256='0'*64 if kind=='hash' else h,usage='validation' if kind=='split' else 'train',max_record_bytes=1 if kind=='cap' else 128*1024**2))
if __name__=='__main__':unittest.main()
