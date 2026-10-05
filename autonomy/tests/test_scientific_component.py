import json,subprocess,sys,tempfile,unittest
from pathlib import Path
import test_scientific_sidecars as fixture

class ScientificComponentCommandTests(unittest.TestCase):
    def test_separate_decode_and_check_commands_reconcile_native_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=fixture.ScientificSidecarTests().source(root);decoded=root/'decoded';checked=root/'check.json'
            a=subprocess.run([sys.executable,'-m','pipeline.scientific_component','decode',str(source),'lidar_pose','scene',str(decoded),'100000'],capture_output=True,text=True)
            self.assertEqual(a.returncode,0,a.stderr)
            b=subprocess.run([sys.executable,'-m','pipeline.scientific_component','validate',str(source),str(decoded),str(checked)],capture_output=True,text=True)
            self.assertEqual(b.returncode,0,b.stderr);self.assertEqual(json.loads(checked.read_text())['rows'],2)
            manifest=json.loads((decoded/'manifest.json').read_text());(decoded/manifest['rows'][0]['metadata']).write_text('{}')
            c=subprocess.run([sys.executable,'-m','pipeline.scientific_component','validate',str(source),str(decoded),str(root/'must-not-exist.json')],capture_output=True,text=True)
            self.assertNotEqual(c.returncode,0);self.assertFalse((root/'must-not-exist.json').exists())

if __name__=='__main__':unittest.main()
