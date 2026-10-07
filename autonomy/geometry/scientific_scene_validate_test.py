import hashlib,json,tempfile,unittest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import shutil
import numpy as np
from test_scientific_reconstruction import ScientificReconstructionTests
from pipeline.scientific_reconstruction import reconstruct_scene
from pipeline.scientific_scene_validate import validate_scene

class ScientificSceneValidationTests(unittest.TestCase):
    def setup_scene(self,root,**kwargs):
        source,sidecars,hashes=ScientificReconstructionTests().fixture(root,**kwargs)
        output=root/'points';reconstruct_scene(source,sidecars,output,10**7,verified_manifest_hashes=hashes)
        return source,sidecars,hashes,output

    def test_native_records_and_explicit_missing_return(self):
        for missing in (False,True):
            with self.subTest(missing=missing),tempfile.TemporaryDirectory() as tmp:
                s,d,h,o=self.setup_scene(Path(tmp),missing_return=missing)
                result=validate_scene(s,d,o,verified_manifest_hashes=h)
                self.assertEqual(result['records'],10);self.assertEqual(result['points'],9 if missing else 10)
                self.assertLess(result['scalar_max_error_m'],1e-6)

    def test_native_float32_physical_values_promoted_losslessly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s,d,h,o=self.setup_scene(root)
            table=pq.read_table(s)
            for name in table.schema.names:
                if name.endswith('.values'):
                    i=table.schema.get_field_index(name);table=table.set_column(i,name,table[name].cast(pa.list_(pa.float32())))
            pq.write_table(table,s);shutil.rmtree(o)
            reconstruct_scene(s,d,o,10**7,verified_manifest_hashes=h)
            self.assertEqual(validate_scene(s,d,o,verified_manifest_hashes=h)['points'],10)

    def test_orphan_sidecar_sensor_frame_rejected(self):
        from dataset.scientific_sidecars import materialize_component
        for component in ('lidar_pose','lidar_camera_projection','lidar_segmentation'):
            with self.subTest(component=component),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);source,sidecars,hashes,output=self.setup_scene(root)
                native=root/(component+'.parquet');table=pq.read_table(native);extra=table.slice(0,1)
                index=extra.schema.get_field_index('key.frame_timestamp_micros');extra=extra.set_column(index,'key.frame_timestamp_micros',pa.array([20],type=pa.int64()))
                pq.write_table(pa.concat_tables([table,extra]),native);shutil.rmtree(sidecars/component)
                materialize_component(native,component,'scene',sidecars/component,10**7)
                hashes[component]=hashlib.sha256((sidecars/component/'manifest.json').read_bytes()).hexdigest()
                report=output/'report.json';r=json.loads(report.read_text());r['sidecar_manifest_hashes']=hashes;report.write_text(json.dumps(r))
                with self.assertRaises(ValueError):validate_scene(source,sidecars,output,verified_manifest_hashes=hashes)

    def test_rehashed_payload_mutations_rejected(self):
        for field in ('pixels','physical_features','nlz','camera_projection','segmentation','xyz'):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                s,d,h,o=self.setup_scene(Path(tmp));p=o/'report.json';r=json.loads(p.read_text());row=r['rows'][0];artifact=o/row['artifact']
                with np.load(artifact,allow_pickle=False) as a:payload={k:a[k].copy() for k in a.files}
                payload[field].flat[0]+=1;np.savez(artifact,**payload)
                row['sha256']=hashlib.sha256(artifact.read_bytes()).hexdigest();p.write_text(json.dumps(r))
                with self.assertRaises(ValueError):validate_scene(s,d,o,verified_manifest_hashes=h)

    def test_manifest_identity_inventory_and_provenance_mutations_rejected(self):
        for mutation in ('return','source','sidecar','missing','extra','presence','motion','pointcount'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                s,d,h,o=self.setup_scene(Path(tmp));p=o/'report.json';r=json.loads(p.read_text())
                if mutation=='return':r['rows'][0]['return']=2
                elif mutation=='source':r['source_lidar_sha256']='0'*64
                elif mutation=='sidecar':r['sidecar_manifest_hashes']['lidar_pose']='0'*64
                elif mutation=='missing':r['rows'].pop()
                elif mutation=='extra':(o/'orphan.npz').write_bytes(b'extra')
                elif mutation=='presence':r['rows'][0]['return_present']=False
                elif mutation=='motion':r['rows'][0]['motion']='uncompensated'
                elif mutation=='pointcount':r['rows'][0]['points']+=1
                p.write_text(json.dumps(r))
                with self.assertRaises(ValueError):validate_scene(s,d,o,verified_manifest_hashes=h)

if __name__=='__main__':unittest.main()
