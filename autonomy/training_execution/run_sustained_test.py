import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from resources.backend import ResourceBackend
from resources.sources import sha
from training_execution.run_sustained import ResourceNativeBackend, open_backend


class RunSustainedBackendBindingTests(unittest.TestCase):
 def inventory(self,root,record):
  root=Path(root);members={}
  digests={
   'identity.json':'i'*64,
   'checkpoint.json':record['resource_companion_sha256'],
   'native-final.json':record['final_sha256'],
   'producer-report.json':record['report_sha256'],
   'native-manifest.json':'m'*64,
  }
  for name,digest in digests.items():
   path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(name)
   members[name]={'path':str(path),'sha256':digest,'bytes':path.stat().st_size}
  return members

 def backend(self,root):
  backend=ResourceNativeBackend.__new__(ResourceNativeBackend)
  backend.R=root/'case';backend.R.mkdir(parents=True);backend.output=root/'payload';backend.output.mkdir()
  backend.resource_root=backend.R/'resource-layer';(backend.resource_root/'checkpoints').mkdir(parents=True)
  backend.resource_identity_sha256='i'*64;backend.manifest_sha='m'*64
  backend.guard=lambda: None
  return backend

 def record(self,root):
  final=root/'final.json';final.write_text('final')
  report=root/'report.json';report.write_text('report')
  companion=root/'companion.json';companion.write_text('companion')
  payload=root/'payload-root';payload.mkdir()
  return {'step':1000,'target_step':1000,'root':str(payload),'final_path':str(final),'final_sha256':sha(final),'report_snapshot':str(report),'report_sha256':sha(report),'resource_companion_path':str(companion),'resource_companion_sha256':sha(companion),'resource_identity_sha256':'i'*64,'released':False}

 def resource_receipt(self,root,backend,record,inventory,*,independent=True,readback=True):
  pubroot=root/'resource-pub';pubroot.mkdir()
  expected=pubroot/'expected.json';expected.write_text(json.dumps(inventory,sort_keys=True))
  archive='a'*64;members=[{'path':name,'sha256':entry['sha256'],'bytes':entry['bytes']} for name,entry in sorted(inventory.items())]
  payload=sum(member['bytes'] for member in members)
  validation={'archive_sha256':archive,'exact_members_and_hashes':True,'members':len(members),'payload_bytes':payload}
  checks=[]
  for stage in ['create-live','archive-put','archive-get','manifest-put','manifest-get','verify-live','rehydrate-live']:
   check={'stage':stage,'exit_code':0}
   if stage.endswith('-live'):check['validation']={**validation,**({'verified_rehydration':True} if stage=='rehydrate-live' else {})}
   checks.append(check)
  prefix='hdfs://harunava/user/tiger/waystone/sureal/runs/perception-resource-closures/balanced16-fixture'
  chunk={'manifest':{'members':members,'payload_bytes':payload,'archive_sha256':archive},'archive_hdfs_uri':prefix+'/'+archive+'/archive.tar.gz','manifest_hdfs_uri':prefix+'/'+archive+'/manifest.json','checks':checks}
  base={'schema_version':1,'kind':'checkpoint','hdfs_prefix':prefix,'source_inventory':inventory,'source_inventory_sha256':sha(expected),'resource_identity_sha256':backend.resource_identity_sha256,'native_manifest_sha256':backend.manifest_sha,'resource_source_pins':{},'resource_source_directory':str(root/'resources'),'execution_directory':str(root/'execution'),'runtime_lock':{},'rootfs_path':str(root/'rootfs'),'archive_library':{'path':str(root/'archive.py'),'sha256':'b'*64},'chunks':[chunk]}
  readback_value={**base}
  readback_path=pubroot/'publication-readback.json';readback_path.write_text(json.dumps(readback_value if readback else {**readback_value,'kind':'shared'},sort_keys=True))
  pub={**base,'manifest_readback_exact':True,'publication_manifest_hdfs_uri':prefix+'/publication-manifest.json','publication_manifest_sha256':sha(readback_path),'independent_admission':{'exit_code':0 if independent else 1,'validation':{'whole_member_union_exact':independent}}}
  receipt=pubroot/'verified-publication.json';receipt.write_text(json.dumps(pub,sort_keys=True))
  return {'path':str(receipt),'sha256':sha(receipt),'hdfs_manifest_uri':pub['publication_manifest_hdfs_uri'],'kind':'checkpoint'}

 def test_controller_opens_resource_bound_native_backend(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);identity=root/'case/resource-layer/identity.json';identity.parent.mkdir(parents=True)
   def native_init(self,run_id,recipe,lock,*,resume=False):
    self.R=root/'case';self.output=root/'payload';self.output.mkdir();self.manifest_sha='a'*64;self.anchor_sha='b'*64;self._resource_identity=None
   attached=[]
   def attach(self,path,digest):
    attached.append((Path(path),digest));self._resource_identity={'attached':True}
   with patch('training_execution.run_sustained.NativeBackend.__init__',native_init),patch('training_execution.run_sustained.prepare_identity',return_value=(identity,'c'*64)) as prepare,patch.object(ResourceBackend,'attach_resources',attach):
    backend=open_backend('run1','baseline',object(),resume=False)
   self.assertIsInstance(backend,ResourceNativeBackend);self.assertIsInstance(backend,ResourceBackend)
   prepare.assert_called_once_with(backend,root/'case/resource-layer',timeout_for_stage=backend.resource_stage_timeout)
   self.assertEqual(attached,[(identity,'c'*64)])

 def test_resource_publication_precedes_native_release(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);backend=self.backend(root);record=self.record(root);inventory=self.inventory(root,record);events=[]
   def publish(owner,kind,items):
    events.append(('resource',kind));self.assertEqual(items,inventory);return self.resource_receipt(root,backend,record,inventory)
   def native(owner,item):
    events.append(('native',item['resource_publication']['kind']));return {'native':'released'}
   with patch('training_execution.run_sustained.resource_inventory',side_effect=lambda owner,item:(events.append(('inventory',item['target_step'])) or inventory)),patch('training_execution.run_sustained.publish_bundle',side_effect=publish),patch('training_execution.run_sustained.NativeBackend.publish_and_release',side_effect=native):
    result=backend.publish_and_release(record)
   self.assertEqual(result,{'native':'released'});self.assertEqual(events,[('inventory',1000),('resource','checkpoint'),('native','checkpoint')]);self.assertEqual(record['resource_publication']['receipt_sha256'],sha(record['resource_publication']['receipt_path']))

 def test_resource_admission_or_readback_failure_blocks_native_release(self):
  for fault in ['independent','readback']:
   with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
    root=Path(temp);backend=self.backend(root);record=self.record(root);inventory=self.inventory(root,record)
    receipt=self.resource_receipt(root,backend,record,inventory,independent=fault!='independent',readback=fault!='readback')
    with patch('training_execution.run_sustained.resource_inventory',return_value=inventory),patch('training_execution.run_sustained.publish_bundle',return_value=receipt),patch('training_execution.run_sustained.NativeBackend.publish_and_release') as native:
     with self.assertRaises(ValueError):backend.publish_and_release(record)
    native.assert_not_called();self.assertNotIn('resource_publication',record)

 def test_native_release_failure_leaves_recoverable_resource_publication(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);backend=self.backend(root);record=self.record(root);inventory=self.inventory(root,record);receipt=self.resource_receipt(root,backend,record,inventory)
   with patch('training_execution.run_sustained.resource_inventory',return_value=inventory),patch('training_execution.run_sustained.publish_bundle',return_value=receipt),patch('training_execution.run_sustained.NativeBackend.publish_and_release',side_effect=RuntimeError('native release failed')):
    with self.assertRaises(RuntimeError):backend.publish_and_release(record)
   self.assertIn('resource_publication',record);self.assertTrue(Path(record['resource_publication']['sidecar_path']).exists())

 def test_resource_publication_sidecar_resumes_without_republishing(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);backend=self.backend(root);record=self.record(root);inventory=self.inventory(root,record);receipt=self.resource_receipt(root,backend,record,inventory)
   from resources.checkpoint import write_publication_record
   write_publication_record(backend,record,receipt,inventory);record.pop('resource_publication')
   with patch('training_execution.run_sustained.resource_inventory',return_value=inventory),patch('training_execution.run_sustained.publish_bundle') as publish,patch('training_execution.run_sustained.NativeBackend.publish_and_release',return_value={'native':'released'}):
    self.assertEqual(backend.publish_and_release(record),{'native':'released'})
   publish.assert_not_called();self.assertIn('resource_publication',record)

 def test_tampered_retained_resource_proof_refuses_resume(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);backend=self.backend(root);record=self.record(root);inventory=self.inventory(root,record);receipt=self.resource_receipt(root,backend,record,inventory)
   from resources.checkpoint import write_publication_record
   write_publication_record(backend,record,receipt,inventory);record.pop('resource_publication')
   publication=Path(receipt['path']);value=json.loads(publication.read_text());value['source_inventory']['native-final.json']['sha256']='0'*64;publication.write_text(json.dumps(value,sort_keys=True));receipt['sha256']=sha(publication)
   with patch('training_execution.run_sustained.resource_inventory',return_value=inventory),patch('training_execution.run_sustained.publish_bundle') as publish,patch('training_execution.run_sustained.NativeBackend.publish_and_release') as native:
    with self.assertRaises(ValueError):backend.publish_and_release(record)
   publish.assert_not_called();native.assert_not_called()

 def test_check_record_recovers_completed_native_release_and_validates_resource_identity(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);backend=self.backend(root);record=self.record(root);inventory=self.inventory(root,record);receipt=self.resource_receipt(root,backend,record,inventory)
   from resources.checkpoint import write_publication_record
   write_publication_record(backend,record,receipt,inventory);record.pop('resource_publication')
   Path(record['root']).rmdir();cache=root/'cache';release_dir=cache/'insula/hdfs-retention-fixture';release_dir.mkdir(parents=True)
   publication=release_dir/'verified-publication.json';publication.write_text(json.dumps({'parent_receipts':{record['final_path']:record['final_sha256']},'independent_admission':{'exit_code':0,'validation':{'whole_member_union_exact':True}},'publication_manifest_hdfs_uri':'hdfs://native/manifest'},sort_keys=True))
   release=release_dir/'release-completed.json';release.write_text(json.dumps({'publication_receipt_sha256':sha(publication),'released':[{'local_path':str(root/'already-gone')}]},sort_keys=True))
   with patch('training_execution.run_sustained.C',cache),patch.object(ResourceBackend,'check_record') as parent:
    backend.check_record(record,None)
   parent.assert_called_once();self.assertTrue(record['released']);self.assertIn('resource_publication',record);self.assertEqual(record['publication']['publication_sha256'],sha(publication))


if __name__=='__main__':unittest.main()
