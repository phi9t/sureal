import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from test_scientific_reconstruction import ScientificReconstructionTests as Fixture

class ScientificSceneCommandTests(unittest.TestCase):
    def test_separate_commands_and_no_failed_validation_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,sidecars,hashes=Fixture().fixture(root)
            provenance=root/'trusted.json';provenance.write_text(json.dumps(hashes));points=root/'points';check=root/'checked.json'
            command=[sys.executable,'-m','pipeline.scientific_scene_command']
            p=subprocess.run(command+['reconstruct',str(source),str(sidecars),str(provenance),str(points),'10000000'],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run(command+['validate',str(source),str(sidecars),str(provenance),str(points),str(check)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(check.read_text())['points'],10)
            # Refuse overwriting already published checker output.
            before=check.read_bytes();p=subprocess.run(command+['validate',str(source),str(sidecars),str(provenance),str(points),str(check)],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0);self.assertEqual(check.read_bytes(),before)
            record=points/'report.json';r=json.loads(record.read_text());r['source_lidar_sha256']='0'*64;record.write_text(json.dumps(r));failed=root/'failed.json'
            p=subprocess.run(command+['validate',str(source),str(sidecars),str(provenance),str(points),str(failed)],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0);self.assertFalse(failed.exists())

if __name__=='__main__':unittest.main()
