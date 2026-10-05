import base64,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import pyarrow as pa,pyarrow.parquet as pq
from pipeline.native_range_shape_file import read_native_range_shapes
class FileTests(unittest.TestCase):
 def fixture(self,p):
  r={'key.segment_context_name':'scene','key.frame_timestamp_micros':10,'key.laser_name':1,'[LiDARComponent].range_image_return1.shape':[64,2650,4],'[LiDARComponent].range_image_return2.shape':None,'[LiDARComponent].range_image_return1.values':[1.,2.,3.,4.]}
  pq.write_table(pa.Table.from_pylist([r]),p);data=p.read_bytes();source={'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'md5_base64':base64.b64encode(hashlib.md5(data).digest()).decode()};keys={k:r[k] for k in r if k.startswith('key.')};inventory={'rows':1,'key_sha256':hashlib.sha256((json.dumps(keys,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()};return source,inventory
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
