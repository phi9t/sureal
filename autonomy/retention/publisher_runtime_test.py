import json
import tempfile
import unittest
from pathlib import Path

from resources.resource_archive import sha
from retention.publisher_runtime import admitted_host_sources,stage_audit_source


class PublisherRuntimeTests(unittest.TestCase):
 def write_receipt(self,root,relative,*,schema_version):
  root=Path(root)
  member=('autonomy/'+relative) if schema_version==2 else relative
  path=root/member
  path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text('admitted audit\n')
  receipt={'schema_version':schema_version,'source_snapshot_root':str(root),'source_pins':{member:sha(path)}}
  receipt_path=root.parent/'receipt.json'
  receipt_path.write_text(json.dumps(receipt,sort_keys=True))
  return receipt_path,receipt

 def test_supplied_schema2_receipt_stages_audit_from_canonical_member_without_freezing(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'snapshot'
   receipt_path,receipt=self.write_receipt(root,'retention/checkpoint_retention_audit.py',schema_version=2)
   def freeze(*args,**kwargs):
    raise AssertionError('publisher child must not create a fresh host snapshot')
   calls=[]
   def validate(repository,pins):
    calls.append((Path(repository),pins))
    return {'source_files':1}
   host_pins,package=admitted_host_sources(receipt_path,root/'autonomy',Path(temp)/'unused-freeze',freeze,validate)
   self.assertEqual(host_pins,receipt)
   self.assertEqual(package,root/'autonomy')
   staged=stage_audit_source(host_pins,Path(temp)/'source','retention/checkpoint_retention_audit.py')
   self.assertEqual(staged.read_text(),'admitted audit\n')
   self.assertEqual(calls,[(root/'autonomy',receipt)])
   self.assertFalse((Path(temp)/'source/autonomy').exists())

 def test_supplied_legacy_receipt_stages_audit_from_component_member_without_freezing(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'legacy'
   receipt_path,receipt=self.write_receipt(root,'retention/cache_retention_audit.py',schema_version=1)
   def freeze(*args,**kwargs):
    raise AssertionError('publisher child must not create a fresh host snapshot')
   def validate(repository,pins):
    return {'source_files':1}
   host_pins,package=admitted_host_sources(receipt_path,root,Path(temp)/'unused-freeze',freeze,validate)
   self.assertEqual(host_pins,receipt)
   self.assertEqual(package,root)
   staged=stage_audit_source(host_pins,Path(temp)/'source','retention/cache_retention_audit.py')
   self.assertEqual(staged.read_text(),'admitted audit\n')

 def test_supplied_receipt_must_execute_from_its_materialized_package(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'snapshot'
   receipt_path,_=self.write_receipt(root,'retention/pilot_retention_audit.py',schema_version=2)
   with self.assertRaisesRegex(ValueError,'admitted host source package root'):
    admitted_host_sources(receipt_path,Path(temp)/'checkout',Path(temp)/'unused-freeze',lambda *a,**k: None,lambda *a,**k: None)


if __name__=='__main__':unittest.main()
