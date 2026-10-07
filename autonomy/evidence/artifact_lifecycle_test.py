import tempfile,unittest
from pathlib import Path
from evidence.artifact_lifecycle import admit_artifact
class LifecycleTests(unittest.TestCase):
 def test_undeclared_delete_refused(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):admit_artifact(Path(d)/'missing','bad',{},set())
 def test_declared_release(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'released';self.assertEqual(admit_artifact(p,'h',{str(p):'h'},set()),'declared release')
 def test_declared_supersession(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'model';p.write_bytes(b'new');self.assertEqual(admit_artifact(p,'old',{}, {'old'}),'declared supersession')
 def test_immutable_hash_required(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'head';p.write_bytes(b'bad')
   with self.assertRaises(ValueError):admit_artifact(p,'wrong',{},set())
