import base64,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from geometry.native_range_shape_file import read_native_range_shapes
from geometry.native_range_shape_test_fixtures import native_range_shape_fixture
class FileTests(unittest.TestCase):
 def fixture(self,p):
  return native_range_shape_fixture(p)
 def test_source_pinned_shape_extraction(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'source.parquet';source,inventory=self.fixture(p);r=read_native_range_shapes(p,scene='scene',source=source,inventory=inventory);self.assertEqual(r['source'],source);self.assertEqual(r['shapes']['native_rows'],1);self.assertIsNone(r['shapes']['records'][1]['native_shape']);self.assertNotIn('values',json.dumps(r['shapes']))
 def test_changed_bytes_refused_before_parquet_decode(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'source.parquet';source,inventory=self.fixture(p)
   for k,v in [('sha256','0'*64),('size_bytes',source['size_bytes']+1),('md5_base64',base64.b64encode(b'0'*16).decode())]:
    with patch('pyarrow.parquet.ParquetFile') as decode,self.assertRaises(ValueError):read_native_range_shapes(p,scene='scene',source=dict(source,**{k:v}),inventory=inventory)
    decode.assert_not_called()
   link=Path(tmp)/'link';link.symlink_to(p)
   with self.assertRaises(ValueError):read_native_range_shapes(link,scene='scene',source=source,inventory=inventory)
if __name__=='__main__':unittest.main()
