import copy,tempfile,unittest
from pathlib import Path
from test_native_range_shape_file import FileTests
from pipeline.native_range_shape_file import read_native_range_shapes
from pipeline.native_range_shape_reference import verify_native_range_shapes
class ReferenceTests(unittest.TestCase):
 def test_complete_native_report_and_rehashed_mutations(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'source.parquet';source,inventory=FileTests().fixture(p);report=read_native_range_shapes(p,scene='scene',source=source,inventory=inventory)['shapes']
   result=verify_native_range_shapes(p,report,scene='scene',source=source,inventory=inventory);self.assertEqual(result['records_verified'],2)
   mutations=[('shape',None),('dimension',None),('return',None),('drop',None),('counts',None),('keyhash',None)]
   for name,_ in mutations:
    bad=copy.deepcopy(report)
    if name=='shape':bad['records'][1]['native_shape']=[64,2650,4]
    if name=='dimension':bad['records'][0]['native_shape']=[64,2649,4]
    if name=='return':bad['records'][0]['return']=2
    if name=='drop':bad['records'].pop()
    if name=='counts':bad['present_shape_records']=2;bad['null_shape_records']=0
    if name=='keyhash':bad['key_sha256']='0'*64
    with self.subTest(name=name),self.assertRaises(ValueError):verify_native_range_shapes(p,bad,scene='scene',source=source,inventory=inventory)
 def test_changed_source_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'source.parquet';source,inventory=FileTests().fixture(p);report=read_native_range_shapes(p,scene='scene',source=source,inventory=inventory)['shapes'];p.write_bytes(b'changed')
   with self.assertRaises(ValueError):verify_native_range_shapes(p,report,scene='scene',source=source,inventory=inventory)
if __name__=='__main__':unittest.main()
