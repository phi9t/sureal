import copy,hashlib,json,os,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from evidence.source_snapshot import LocalSnapshotStore,archive_sources
from training_execution import admit_sustained, sustained_controller_backend
from training_execution.sustained_controller_backend import NativeBackend,sha
from training_execution.sustained_controller_sources import REQUIRED as HOST_REQUIRED,freeze_host_sources
from retention.checkpoint_retention_sources import REQUIRED as CHECKPOINT_PUBLISHER_REQUIRED
from retention.checkpoint_retention_sources import freeze_host_sources as freeze_checkpoint_publisher_sources
from training_execution.sustained_sources import REQUIRED as PACKAGE_REQUIRED,SNAPSHOT_TARGET
class ControllerGuardTests(unittest.TestCase):
 def test_live_admission_uses_current_locked_runtime_roots(self):
  self.assertEqual(sustained_controller_backend.GPU_ROOT.name,'gpu-rootfs-v6')
  self.assertEqual(sustained_controller_backend.CPU_ROOT.name,'rootfs-v4')
  self.assertEqual(admit_sustained.GPU_ROOT.name,'gpu-rootfs-v6')
  self.assertEqual(admit_sustained.CPU_ROOT.name,'rootfs-v4')

 def test_current_gpu_runtime_lock_comes_from_v6_lock_not_historical_receipt(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);gpu=root/'gpu-rootfs-v6';gpu.mkdir()
   lock={'schema_version':1,'rootfs_sha256':'5'*64,'image_id':'current-v6'}
   Path(str(gpu)+'.lock.json').write_text(json.dumps(lock))
   old={'runtime_lock':{'rootfs_sha256':'4'*64,'image_id':'old'}}
   with patch('training_execution.sustained_controller_backend.GPU_ROOT',gpu),patch('training_execution.sustained_controller_backend.verify_rootfs') as verify:
    self.assertEqual(sustained_controller_backend.current_gpu_runtime_lock(old),lock)
   verify.assert_called_once_with(gpu,lock['rootfs_sha256'])
   with patch('training_execution.admit_sustained.GPU_ROOT',gpu),patch('training_execution.admit_sustained.verify_rootfs') as verify:
    self.assertEqual(admit_sustained.current_gpu_runtime_lock(old),lock)
   verify.assert_called_once_with(gpu,lock['rootfs_sha256'])

 def test_gpu_stage_command_rebinds_historical_rootfs_to_current_gpu_root(self):
  command=['bwrap','--ro-bind','/old/gpu-rootfs','/','--ro-bind','/old/code','/experiment','--bind','/old/out','/outputs','--','python','old.py']
  expected_root='/current/gpu-rootfs-v6'
  rewritten=sustained_controller_backend.rebind_rootfs_mount(command,expected_root)
  self.assertEqual(command[2],'/old/gpu-rootfs')
  self.assertEqual(rewritten[2],expected_root)
  self.assertEqual(rewritten[5],'/old/code')
  with self.assertRaises(ValueError):
   sustained_controller_backend.rebind_rootfs_mount(['bwrap','--','python'],expected_root)

 def source_snapshot(self,root,names,store_root):
  archive,pins=archive_sources(root,names);digest=hashlib.sha256(archive).hexdigest();LocalSnapshotStore(store_root).store(digest,archive)
  return {'schema_version':1,'source_snapshot_sha256':digest,'source_snapshot_target':SNAPSHOT_TARGET,'source_snapshot_store':str(store_root),'source_pins':pins}
 def query_runner(self,names):
  def run(command,**kwargs):
   self.assertIn('query',command)
   class Result:pass
   result=Result()
   result.stdout=''.join('//'+name.rsplit('/',1)[0]+':'+name.rsplit('/',1)[1]+'\n' for name in sorted(names))
   return result
  return run
 def checkout(self,root,anchor_sha):
  repo=Path(root)
  autonomy=repo if repo.name=='autonomy' else repo/'autonomy'
  for name in HOST_REQUIRED:
   path=autonomy/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('host '+name)
  (autonomy/'research').mkdir(exist_ok=True)
  (autonomy/'research/training-anchor-candidate-verified.json').write_text(json.dumps({'expected':{'candidate_sha256':anchor_sha}}))
  return autonomy
 def backend(self,root,checkout=None):
  root.mkdir(parents=True,exist_ok=True)
  b=NativeBackend.__new__(NativeBackend);b.R=root;b.package=root/'code';b.package.mkdir();b.verifier=root/'verifier';b.verifier.mkdir();b.source=root/'input';b.source.mkdir();(b.source/'manifest.json').write_text('{}');b.manifest_sha=sha(b.source/'manifest.json');b.runtime={'rootfs_sha256':'1'*64,'image_id':'gpu'};b.cpu_runtime={'rootfs_sha256':'3'*64,'image_id':'cpu'};b.metric_runtime={'rootfs_sha256':'2'*64,'image_id':'metrics'};b.runtime_path=root/'runtime.json';b.runtime_path.write_text(json.dumps(b.runtime));b.output=root/'payload';b.output.mkdir();b.host_pins={};b.old={'driver_hashes':{}};b.pins={}
  for name in PACKAGE_REQUIRED:
   p=b.package/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('original '+name)
  for name in ['audit_sustained_transition.py','sustained_chunk_reference.py']:
   p=b.package/'training_execution'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('original '+name);q=b.verifier/name;q.write_bytes(p.read_bytes());b.pins['training_execution/'+name]=sha(p)
  b.pins=self.source_snapshot(b.package,sorted(str(p.relative_to(b.package)) for p in b.package.rglob('*.py')),root/'source-snapshots')
  (b.source/'anchor-templates.json').write_text('admitted anchors');b.anchor_sha=sha(b.source/'anchor-templates.json');b.verifier_pins={str(p):sha(p) for p in b.verifier.iterdir()}
  checkout=root/'checkout' if checkout is None else checkout
  autonomy=self.checkout(checkout,b.anchor_sha);repo=autonomy.parent
  b.checkout_path=autonomy
  b.host_pins=freeze_host_sources(autonomy,root/'host-source',store=LocalSnapshotStore(root/'host-source-snapshots'),repo_root=repo,bazel=repo/'bazelw',runner=self.query_runner(['autonomy/'+name for name in HOST_REQUIRED]))
  b.checkpoint_publisher_pins=freeze_checkpoint_publisher_sources(autonomy,root/'checkpoint-publisher-source',store=LocalSnapshotStore(root/'checkpoint-publisher-source-snapshots'),repo_root=repo,bazel=repo/'bazelw',runner=self.query_runner(['autonomy/'+name for name in CHECKPOINT_PUBLISHER_REQUIRED]))
  return b
 def guard(self,b):
  with patch('training_execution.sustained_controller_backend.P',b.checkout_path),patch('training_execution.sustained_controller_backend.unique_payload_bytes',return_value=0):b.guard()
 def test_current_checkout_edit_and_path_change_do_not_invalidate_snapshot_guard(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);checkout_a=root/'checkout-a';b=self.backend(root/'run',checkout_a)
   with patch('training_execution.sustained_controller_backend.P',b.checkout_path),patch('training_execution.sustained_controller_backend.unique_payload_bytes',return_value=0):
    b.guard();(b.checkout_path/'training_execution/unrelated.py').write_text('new checkout helper\n');b.guard()
   checkout_b=root/'checkout-b';shutil.copytree(checkout_a,checkout_b);moved=checkout_b/'autonomy'
   with patch('training_execution.sustained_controller_backend.P',moved),patch('training_execution.sustained_controller_backend.unique_payload_bytes',return_value=0):b.guard()
 def test_altered_or_missing_source_snapshot_invalidates_guard(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);b=self.backend(root/'run',root/'checkout')
   snapshot=Path(b.pins['source_snapshot_store'])/b.pins['source_snapshot_sha256']
   with patch('training_execution.sustained_controller_backend.P',b.checkout_path),patch('training_execution.sustained_controller_backend.unique_payload_bytes',return_value=0):b.guard()
   snapshot.write_bytes(b'not the admitted snapshot')
   with patch('training_execution.sustained_controller_backend.P',b.checkout_path),patch('training_execution.sustained_controller_backend.unique_payload_bytes',return_value=0),self.assertRaises(ValueError):b.guard()
   snapshot.unlink()
   with patch('training_execution.sustained_controller_backend.P',b.checkout_path),patch('training_execution.sustained_controller_backend.unique_payload_bytes',return_value=0),self.assertRaises(FileNotFoundError):b.guard()
 def test_guard_restores_missing_native_host_and_publisher_snapshots_from_receipts(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);b=self.backend(root/'run',root/'checkout')
   original={'native':copy.deepcopy(b.pins),'host':copy.deepcopy(b.host_pins),'publisher':copy.deepcopy(b.checkpoint_publisher_pins)}
   roots=[b.package,Path(b.host_pins['source_snapshot_root']),Path(b.checkpoint_publisher_pins['source_snapshot_root'])]
   for materialized in roots:
    shutil.rmtree(materialized)
    self.assertFalse(materialized.exists())
   with patch('training_execution.sustained_controller_backend.P',b.checkout_path),patch('training_execution.sustained_controller_backend.unique_payload_bytes',return_value=0):
    b.guard()
   for materialized in roots:
    self.assertTrue(materialized.is_dir())
   self.assertEqual(b.pins,original['native'])
   self.assertEqual(b.host_pins,original['host'])
   self.assertEqual(b.checkpoint_publisher_pins,original['publisher'])
 def test_changed_decoder_anchors_refused_before_stage_or_resume(self):
  with tempfile.TemporaryDirectory() as temp:
   b=self.backend(Path(temp));self.guard(b);(b.source/'anchor-templates.json').write_text('different decoder')
   with self.assertRaises(ValueError):self.guard(b)
 def test_verifier_copy_matches_frozen_source(self):
  with tempfile.TemporaryDirectory() as temp:self.guard(self.backend(Path(temp)))
 def test_resume_cannot_rebaseline_a_tampered_verifier(self):
  with tempfile.TemporaryDirectory() as temp:
   b=self.backend(Path(temp));p=b.verifier/'sustained_chunk_reference.py';p.write_text('changed independent math');b.verifier_pins[str(p)]=sha(p)
   with self.assertRaises(ValueError):self.guard(b)
 def test_foreign_stage_runtime_worker_and_code_mount_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   b=self.backend(Path(temp));inputs=b.R/'train-1000-input';inputs.mkdir();manifest=inputs/'manifest.json';manifest.write_text('{}');artifact=b.output/'live.log';artifact.write_text('fixture');receipt={'stage':'train-1000','requested_stage':'train-1000','exit_code':0,'manifest_sha256':b.manifest_sha,'source_hashes':b.pins,'runtime_lock':b.runtime,'driver_hashes':{},'verifier_source_pins':{},'input_hashes':{str(manifest):sha(manifest)},'artifacts':{str(artifact):sha(artifact)},'output_directory':str(b.output),'command':['bwrap','--ro-bind',str(sustained_controller_backend.GPU_ROOT),'/','--ro-bind',str(b.package),'/experiment','--ro-bind',str(inputs),'/source','--ro-bind',str(inputs),'/tmp/inputs','--bind',str(b.output),'/outputs','--ro-bind',str(b.R/'source-snapshots'),'/tmp/source-snapshots','--setenv','SUREAL_SOURCE_SNAPSHOT_STORE','/tmp/source-snapshots','--','/experiment/training_execution/train_sustained.py']};b.check_stage(receipt)
   for fault in ['runtime','worker','mount','snapshot-store','empty-inputs','empty-artifacts']:
    bad=copy.deepcopy(receipt)
    if fault=='runtime':bad['runtime_lock']=b.metric_runtime
    elif fault=='worker':bad['command'][-1]='/experiment/unsafe.py'
    elif fault=='mount':bad['command'][bad['command'].index('/experiment')-1]=str(b.R/'foreign')
    elif fault=='snapshot-store':bad['command'][bad['command'].index('/tmp/source-snapshots')-1]=str(b.R/'foreign-snapshots')
    elif fault=='empty-inputs':bad['input_hashes']={}
    else:bad['artifacts']={}
    with self.assertRaises(ValueError):b.check_stage(bad)
 def test_checkpoint_publisher_runs_as_module_without_inherited_pythonpath(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);b=self.backend(root/'run',root/'checkout');cache=root/'cache';(cache/'insula').mkdir(parents=True);payload=root/'payload-root';heads=payload/'heads';heads.mkdir(parents=True);native=payload/'checkpoint.pt';native.write_text('native bytes');report=payload/'check.json';head_hashes={}
   for index in range(16):
    head=heads/f'heads-{index:02d}.npz';head.write_text(f'head {index}');head_hashes[head.name]=sha(head)
   live=payload/'live.log';live.write_text('train log')
   producer={'head_hashes':head_hashes};report.write_text(json.dumps(producer))
   train_receipt=b.R/'train-1000-verified.json';train_receipt.write_text(json.dumps({'stage':'train-1000','artifacts':{str(native):sha(native),str(report):sha(report),str(live):sha(live),**{str(heads/name):digest for name,digest in head_hashes.items()}}}))
   final=b.R/'final.json';final.write_text(json.dumps({'stage_receipts':{'train':{'path':str(train_receipt),'sha256':sha(train_receipt)}}}))
   record={'step':1000,'root':str(payload),'checkpoint_sha256':sha(native),'report_sha256':sha(report),'report':producer,'final_path':str(final),'final_sha256':sha(final)}
   lock=(root/'lock').open('w')
   b.lock=lock
   try:
    def run(command,**kwargs):
     self.assertEqual(command[:3],[os.sys.executable,'-m','retention.publish_sustained_checkpoint'])
     self.assertIn('--host-source-receipt',command)
     receipt_path=Path(command[command.index('--host-source-receipt')+1])
     self.assertEqual(json.loads(receipt_path.read_text()),b.checkpoint_publisher_pins)
     self.assertEqual(kwargs['cwd'],Path(b.checkpoint_publisher_pins['source_snapshot_root'])/'autonomy')
     self.assertNotIn('PYTHONPATH',kwargs['env'])
     self.assertEqual(kwargs['pass_fds'],(lock.fileno(),))
     self.assertEqual(kwargs['timeout'],3600)
     directory=cache/'insula/hdfs-retention-fixture';directory.mkdir()
     plan=[{'path':str(p.relative_to(payload)),'local_path':str(p),'sha256':sha(p),'bytes':p.stat().st_size,'archive_hdfs_uri':'hdfs://native/archive.tar.gz'} for p in sorted(payload.rglob('*')) if p.is_file()]
     manifest={'members':[{key:entry[key] for key in ['path','sha256','bytes']} for entry in plan],'payload_bytes':sum(entry['bytes'] for entry in plan),'archive_sha256':'a'*64}
     publication=directory/'verified-publication.json';publication.write_text(json.dumps({'parent_receipts':{str(final):sha(final)},'source_sha256':{entry['path']:entry['sha256'] for entry in plan},'chunks':[{'archive_hdfs_uri':'hdfs://native/archive.tar.gz','manifest':manifest}],'independent_admission':{'exit_code':0,'validation':{'whole_member_union_exact':True}},'publication_manifest_hdfs_uri':'hdfs://native/manifest','release_plan':plan}))
     for entry in plan:Path(entry['local_path']).unlink()
     release=directory/'release-completed.json';release.write_text(json.dumps({'publication_receipt_sha256':sha(publication),'released':plan},indent=2))
     class Result:returncode=0
     return Result()
    with patch('training_execution.sustained_controller_backend.C',cache),patch('training_execution.sustained_controller_backend.P',b.checkout_path),patch.object(b,'guard'),patch.dict(os.environ,{'PYTHONPATH':'unexpected'},clear=False),patch('training_execution.sustained_controller_backend.subprocess.run',side_effect=run):
     result=b.publish_and_release(record)
    self.assertEqual(result['command'][:3],[os.sys.executable,'-m','retention.publish_sustained_checkpoint'])
    self.assertIn('--host-source-receipt',result['command'])
    self.assertEqual(result['publication_sha256'],sha(result['publication_path']))
   finally:
    lock.close()
if __name__=='__main__':unittest.main()
