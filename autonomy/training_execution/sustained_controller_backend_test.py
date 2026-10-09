import copy,hashlib,json,os,shutil,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from blob_store.core import BlobStore,LocalFileBlobAdapter
from evidence.source_snapshot import LocalSnapshotStore,archive_sources
from insula.launch_plan import RuntimeLock
from insula.runtime_roots import CURRENT_CPU_ROOTFS_NAME, CURRENT_GPU_ROOTFS_NAME
from training_execution import admit_sustained, sustained_controller_backend
from training_execution.sustained_controller_backend import NativeBackend,sha
from training_execution.sustained_controller_backend import validate_native_publication_release
from training_execution.sustained_controller_sources import REQUIRED as HOST_REQUIRED,freeze_host_sources
from retention.publication_sources import CHECKPOINT_REQUIRED as CHECKPOINT_PUBLISHER_REQUIRED
from retention.publication_sources import freeze_checkpoint_sources as freeze_checkpoint_publisher_sources
from training_execution.sustained_sources import REQUIRED as PACKAGE_REQUIRED,SNAPSHOT_TARGET
class ControllerGuardTests(unittest.TestCase):
 def native_release_fixture(self,root):
  payload=root/'payload';heads=payload/'heads';heads.mkdir(parents=True)
  (payload/'checkpoint.pt').write_text('checkpoint bytes\n')
  (payload/'live.log').write_text('producer log\n')
  head_hashes={}
  for index in range(16):
   head=heads/f'heads-{index:02d}.npz';head.write_text(f'head {index}\n');head_hashes[head.name]=sha(head)
  report={'head_hashes':head_hashes,'checkpoint_sha256':sha(payload/'checkpoint.pt')}
  (payload/'check.json').write_text(json.dumps(report,sort_keys=True))
  artifacts={str(path):sha(path) for path in sorted(payload.rglob('*')) if path.is_file()}
  train=root/'train-1000.json';train.write_text(json.dumps({'stage':'train-1000','artifacts':artifacts},sort_keys=True))
  final=root/'final.json';final.write_text(json.dumps({'stage_receipts':{'train':{'path':str(train),'sha256':sha(train)}}},sort_keys=True))
  record={'step':1000,'root':str(payload),'checkpoint_sha256':sha(payload/'checkpoint.pt'),
          'report_sha256':sha(payload/'check.json'),'report':report,
          'final_path':str(final),'final_sha256':sha(final)}
  return payload,record

 def test_native_release_reader_accepts_blob_publication_receipt_shape(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);payload,record=self.native_release_fixture(root)
   store_root=root/'blob-store';store=BlobStore(LocalFileBlobAdapter(store_root),backoff_seconds=())
   entries={}
   for path in sorted(payload.rglob('*')):
    if path.is_file():
     name=path.relative_to(payload).as_posix()
     entries[name]={'sha256':sha(path),'bytes':path.stat().st_size}
   archive=root/'archive-000.tar.gz'
   with tarfile.open(archive,'w:gz') as output:
    for name in sorted(entries):
     output.add(payload/name,arcname=name)
   chunk=store.put('checkpoints/perception-sustained-checkpoints/run-step1000/checkpoint/archive-000.tar.gz',archive)
   manifest={'schema_version':1,'area':'checkpoints','child':'perception-sustained-checkpoints',
             'run_id':'run-step1000','kind':'checkpoint','mode':'archive',
             'inventory':entries,'chunks':[chunk]}
   manifest_path=root/'manifest.json';manifest_path.write_text(json.dumps(manifest,sort_keys=True))
   manifest_blob=store.put('checkpoints/perception-sustained-checkpoints/run-step1000/checkpoint/manifest.json',manifest_path)
   publication=root/'verified-publication.json'
   publication.write_text(json.dumps({'schema_version':1,'store_descriptor':{'kind':'local','root':str(store_root)},
                                      'tool_sha256':{'waystone-cli':'a'*64},
                                      'verified_by_readback':True,
                                      'blobs':{'manifest':manifest_blob,'chunks':[chunk]}},sort_keys=True))
   release_plan=[]
   for name,entry in sorted(entries.items()):
    local=payload/name
    release_plan.append({'path':name,'local_path':str(local),'sha256':entry['sha256'],
                         'bytes':entry['bytes'],'archive_blob_key':chunk['key']})
   for entry in release_plan:Path(entry['local_path']).unlink()
   release=root/'release-completed.json'
   release.write_text(json.dumps({'publication_receipt_sha256':sha(publication),'released':release_plan},sort_keys=True))

   value,release_value,plan=validate_native_publication_release(record,publication,release,completed=True)

   self.assertEqual(value['blobs']['manifest']['key'],manifest_blob['key'])
   self.assertEqual(release_value['released'],release_plan)
   self.assertEqual(plan,release_plan)

 def test_live_admission_uses_current_locked_runtime_roots(self):
  self.assertEqual(sustained_controller_backend.GPU_ROOT.name,CURRENT_GPU_ROOTFS_NAME)
  self.assertEqual(sustained_controller_backend.CPU_ROOT.name,CURRENT_CPU_ROOTFS_NAME)
  self.assertEqual(admit_sustained.GPU_ROOT.name,CURRENT_GPU_ROOTFS_NAME)
  self.assertEqual(admit_sustained.CPU_ROOT.name,CURRENT_CPU_ROOTFS_NAME)

 def test_sustained_runtime_locks_are_loaded_through_launch_plan_module(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);gpu=root/CURRENT_GPU_ROOTFS_NAME;cpu=root/CURRENT_CPU_ROOTFS_NAME;metrics=root/'metrics-rootfs-v2'
   for path in [gpu,cpu,metrics]:path.mkdir()
   values=[
    RuntimeLock(gpu,Path(str(gpu)+'.lock.json'),{'rootfs_sha256':'5'*64},'recipe-digest','g'*64),
    RuntimeLock(cpu,Path(str(cpu)+'.lock.json'),{'rootfs_sha256':'6'*64},'recipe-digest','c'*64),
    RuntimeLock(metrics,Path(str(metrics)+'.lock.json'),{'rootfs_sha256':'7'*64,'image_id':'metrics'},'image','m'*64),
   ]
   with patch('training_execution.sustained_controller_backend.GPU_ROOT',gpu),patch('training_execution.sustained_controller_backend.CPU_ROOT',cpu),patch('training_execution.sustained_controller_backend.METRICS_ROOT',metrics),patch('training_execution.sustained_controller_backend.load_default_runtime_lock',side_effect=values) as load,patch.object(NativeBackend,'guard'),patch('training_execution.sustained_controller_backend.reserve_write'),patch('training_execution.sustained_controller_backend.freeze_host_sources',return_value={}),patch('training_execution.sustained_controller_backend.freeze_checkpoint_publisher_sources',return_value={}),patch('training_execution.sustained_controller_backend.snapshot_sources',return_value={'source_snapshot_sha256':'s'*64,'source_snapshot_root':str(root/'code'),'source_pins':{}}),patch('training_execution.sustained_controller_backend.cache_snapshot_for_runtime'),patch('training_execution.sustained_controller_backend.shutil.copyfile'):
    (root/'code/autonomy/training_execution').mkdir(parents=True)
    (root/'code/autonomy/training_execution/audit_sustained_transition.py').write_text('audit\n')
    (root/'code/autonomy/training_execution/sustained_chunk_reference.py').write_text('reference\n')
    (root/'research').mkdir()
    (root/'research/training-anchor-templates.candidate.json').write_text('anchors\n')
    (root/'research/training-anchor-candidate-verified.json').write_text(json.dumps({'expected':{'candidate_sha256':sha(root/'research/training-anchor-templates.candidate.json')}}))
    (root/'research/balanced16-sustained.candidate.json').write_text('{}')
    cache=root/'cache';scientific=cache/'scientific-processing';native=scientific/'balanced16-native-v2';native.mkdir(parents=True)
    historical=cache/'insula/cohort16-baseline-balanced20261002a';historical.mkdir(parents=True)
    (historical/'run.json').write_text(json.dumps({'manifest':{'frames':[]}}))
    with patch('training_execution.sustained_controller_backend.C',cache),patch('training_execution.sustained_controller_backend.W',scientific),patch('training_execution.sustained_controller_backend.P',root),patch('training_execution.sustained_controller_backend.validate_contract'),patch('training_execution.sustained_controller_backend.validate_sources'):
     backend=NativeBackend('run1','baseline',object())
   self.assertEqual([call.args[0] for call in load.call_args_list],[gpu,cpu,metrics])
   self.assertEqual(backend.runtime,values[0].data)

 def test_gpu_stage_plan_requests_configured_gpu_one_instead_of_replayed_root_mount(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);runtime=RuntimeLock(root/'gpu-rootfs-v7',root/'gpu.lock',{'rootfs_sha256':'1'*64},'recipe-digest','r'*64);runtime.rootfs.mkdir()
   paths={}
   for name in ['package','stage','output','native','physical','boxes','scientific','snapshots']:
    path=root/name;path.mkdir();(path/'file').write_text(name);paths[name]=path
   runtime_path=root/'runtime-lock.json';runtime_path.write_text('{}')
   devices=root/'devices';drivers=root/'drivers';devices.mkdir();drivers.mkdir()
   for name in ['nvidia1','nvidiactl','nvidia-uvm']:(devices/name).write_text(name)
   for name in ['libcuda.so.fixture','libnvidia-ptxjitcompiler.so.fixture','libnvidia-nvvm.so.fixture']:(drivers/name).write_text(name)
   env={'SUREAL_BAZEL_GPU_DEVICES':f"{devices/'nvidia1'}=/dev/nvidia1,{devices/'nvidiactl'}=/dev/nvidiactl,{devices/'nvidia-uvm'}=/dev/nvidia-uvm",'SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS':str(drivers),'SUREAL_BAZEL_GPU_DEVICE_UUIDS':'1=GPU-fixture-1'}
   with patch.dict(os.environ,env,clear=False):
    plan=sustained_controller_backend.build_sustained_stage_plan(runtime,package=paths['package'],stage_source=paths['stage'],output=paths['output'],worker='train_sustained.py',native=paths['native'],physical=paths['physical'],boxes=paths['boxes'],runtime_lock_path=runtime_path,scientific_root=paths['scientific'],source_snapshot_store=paths['snapshots'],gpu_index=1)
   record=sustained_controller_backend.record_plan(plan)
   self.assertEqual(record['gpu']['requested_index'],1)
   self.assertEqual(record['command'],['python','/experiment/training_execution/train_sustained.py'])

 def test_gpu_stage_receipt_rechecks_driver_hashes_from_launch_plan(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);b=self.backend(root/'run',root/'checkout');b.gpu_index=1
   runtime=RuntimeLock(root/'gpu-rootfs-v7',root/'gpu.lock',b.runtime,'recipe-digest','r'*64);runtime.rootfs.mkdir();b.runtime_lock=runtime
   inputs=b.R/'train-1000-input';inputs.mkdir();manifest=inputs/'manifest.json';manifest.write_text('{}')
   for name in ['native','physical','boxes','scientific']:
    path=b.R/name;path.mkdir();setattr(b,name,path)
   devices=root/'devices';drivers=root/'drivers';devices.mkdir();drivers.mkdir()
   for name in ['nvidia1','nvidiactl','nvidia-uvm']:(devices/name).write_text(name)
   for name in ['libcuda.so.fixture','libnvidia-ptxjitcompiler.so.fixture','libnvidia-nvvm.so.fixture']:(drivers/name).write_text(name)
   env={'SUREAL_BAZEL_GPU_DEVICES':f"{devices/'nvidia1'}=/dev/nvidia1,{devices/'nvidiactl'}=/dev/nvidiactl,{devices/'nvidia-uvm'}=/dev/nvidia-uvm",'SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS':str(drivers),'SUREAL_BAZEL_GPU_DEVICE_UUIDS':'1=GPU-fixture-1'}
   with patch.dict(os.environ,env,clear=False):
    plan=sustained_controller_backend.build_sustained_stage_plan(runtime,package=b.package,stage_source=inputs,output=b.output,worker='train_sustained.py',native=b.native,physical=b.physical,boxes=b.boxes,runtime_lock_path=b.runtime_path,scientific_root=b.scientific,source_snapshot_store=b.R/'source-snapshots',gpu_index=1,source_snapshot_digest=b.pins['source_snapshot_sha256'])
   command=sustained_controller_backend.render_plan(plan);launch_record=sustained_controller_backend.record_plan(plan)
   driver_hashes={str(path):sha(path) for path in sorted(drivers.iterdir())}
   artifact=b.output/'live.log';artifact.write_text('fixture')
   receipt={'stage':'train-1000','requested_stage':'train-1000','exit_code':0,'manifest_sha256':b.manifest_sha,'source_hashes':b.pins,'runtime_lock':b.runtime,'driver_hashes':driver_hashes,'verifier_source_pins':{},'input_hashes':{str(manifest):sha(manifest)},'artifacts':{str(artifact):sha(artifact)},'output_directory':str(b.output),'command':command,'launch_plan':launch_record}

   b.check_stage(receipt)
   missing=copy.deepcopy(receipt);missing['driver_hashes']={}
   with self.assertRaises(ValueError):b.check_stage(missing)
   (drivers/'libcuda.so.fixture').write_text('swapped libcuda')
   with self.assertRaises(ValueError):b.check_stage(receipt)

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
   snapshot=LocalSnapshotStore(b.pins['source_snapshot_store']).path_for(b.pins['source_snapshot_sha256'])
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
   b=self.backend(Path(temp));inputs=b.R/'train-1000-input';inputs.mkdir();manifest=inputs/'manifest.json';manifest.write_text('{}');artifact=b.output/'live.log';artifact.write_text('fixture');driver=b.R/'libcuda.so.fixture';driver.write_text('driver');receipt={'stage':'train-1000','requested_stage':'train-1000','exit_code':0,'manifest_sha256':b.manifest_sha,'source_hashes':b.pins,'runtime_lock':b.runtime,'driver_hashes':{str(driver):sha(driver)},'verifier_source_pins':{},'input_hashes':{str(manifest):sha(manifest)},'artifacts':{str(artifact):sha(artifact)},'output_directory':str(b.output),'command':['bwrap','--ro-bind',str(sustained_controller_backend.GPU_ROOT),'/','--ro-bind',str(b.package),'/experiment','--ro-bind',str(inputs),'/source','--ro-bind',str(inputs),'/tmp/inputs','--bind',str(b.output),'/outputs','--ro-bind',str(b.R/'source-snapshots'),'/tmp/source-snapshots','--setenv','SUREAL_SOURCE_SNAPSHOT_STORE','/tmp/source-snapshots','--','/experiment/training_execution/train_sustained.py']};b.check_stage(receipt)
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
