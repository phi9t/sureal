import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidence.source_snapshot import LocalSnapshotStore
from insula.entry import launch_plan
from resources.backend import ResourceBackend
from resources.command import wrapped_command
from resources.retention import materialize_execution_package
from resources.retention_audit import LIMIT, validate_union
from resources.sources import sha,validate_sources as validate_resource_sources
from resources.stage import validate_proof
from resources.stage_accounting import MEASUREMENT, admit_worker
from training_execution.run_sustained import ResourceNativeBackend, open_backend


class RunSustainedBackendBindingTests(unittest.TestCase):
 def resource_snapshot_query(self):
  repo=Path(__file__).resolve().parents[2]
  names=sorted(str(path.relative_to(repo)) for path in (repo/'autonomy/resources').glob('*.py') if not path.name.endswith('_test.py'))
  names.append('autonomy/evidence/source_snapshot.py')
  def run(command,**kwargs):
   self.assertIn('query',command)
   class Result:pass
   result=Result()
   result.stdout=''.join('//'+name.rsplit('/',1)[0]+':'+name.rsplit('/',1)[1]+'\n' for name in names)
   return result
  return repo,run

 def inventory(self,root,record):
  root=Path(root);members={}
  for name in ['identity.json','native-manifest.json']:
   path=root/name
   if not path.exists():path.write_text(name)
  paths={
   'identity.json':root/'identity.json',
   'checkpoint.json':Path(record['resource_companion_path']),
   'native-final.json':Path(record['final_path']),
   'producer-report.json':Path(record['report_snapshot']),
   'native-manifest.json':root/'native-manifest.json',
  }
  digests={'checkpoint.json':record['resource_companion_sha256'],
           'native-final.json':record['final_sha256'],
           'producer-report.json':record['report_sha256']}
  for name,path in paths.items():
   digest=digests.get(name,sha(path))
   members[name]={'path':str(path),'sha256':digest,'bytes':path.stat().st_size}
  return members

 def backend(self,root):
  backend=ResourceNativeBackend.__new__(ResourceNativeBackend)
  backend.R=root/'case';backend.R.mkdir(parents=True);backend.output=root/'payload';backend.output.mkdir()
  backend.resource_root=backend.R/'resource-layer';(backend.resource_root/'checkpoints').mkdir(parents=True)
  backend.resource_work_root=root/'scientific';backend.resource_work_root.mkdir()
  backend.resource_reservations=[]
  backend.resource_reserve_write=lambda path,maximum_new_bytes:backend.resource_reservations.append((Path(path),maximum_new_bytes)) or {'used_bytes_before':0,'maximum_new_bytes':maximum_new_bytes}
  identity=root/'identity.json';identity.write_text('identity.json')
  manifest=root/'native-manifest.json';manifest.write_text('native-manifest.json')
  backend._resource_identity=None;backend.resource_identity_sha256=sha(identity);backend.manifest_sha=sha(manifest)
  backend.cpu_runtime={'rootfs_sha256':'f'*64,'image_id':'cpu-fixture'}
  backend.resource_cpu_root=root/'rootfs';backend.resource_cpu_root.mkdir()
  backend.guard=lambda: None
  return backend

 def record(self,root):
  final=root/'final.json';final.write_text('final')
  report=root/'report.json';report.write_text('report')
  companion=root/'companion.json';companion.write_text('companion')
  payload=root/'payload-root';payload.mkdir()
  return {'step':1000,'target_step':1000,'root':str(payload),'final_path':str(final),'final_sha256':sha(final),'report_snapshot':str(report),'report_sha256':sha(report),'resource_companion_path':str(companion),'resource_companion_sha256':sha(companion),'resource_identity_sha256':'i'*64,'released':False}

 def resource_source_fixture(self,root):
  from resources.sources import freeze_sources
  root=Path(root);root.mkdir(parents=True,exist_ok=True)
  package=Path(__file__).resolve().parents[1];source=package/'resources'
  repo,runner=self.resource_snapshot_query()
  pins=freeze_sources(source,root/'resource-source-receipt',store=LocalSnapshotStore(root/'resource-source-snapshots'),repo_root=repo,bazel=repo/'bazelw',runner=runner)
  code=validate_resource_sources(source,pins);execution=root/'execution';library=source/'resource_archive.py'
  materialize_execution_package(code,execution,library,sha(library),pins)
  return source,pins,code,execution,library

 def resource_proof(self,root,code,pins,native_output,inputdir,script,label,argv=(),*,execution=None,library=None,command=None,timeout=300,evidence_dir=None):
  proof_dir=Path(evidence_dir) if evidence_dir is not None else root/'proofs'/label;worker_output=proof_dir/'worker'
  native_output.mkdir(parents=True,exist_ok=True);proof_dir.mkdir(parents=True,exist_ok=evidence_dir is not None);worker_output.mkdir()
  rootfs=root/'rootfs';rootfs.mkdir(exist_ok=True)
  execution=root/'execution' if execution is None else Path(execution)
  library=root/'archive.py' if library is None else Path(library)
  if not library.exists():library.write_text('archive helper\n')
  original=command.copy() if command is not None else ['bwrap','--unshare-all','--die-with-parent',
                                                       '--ro-bind',str(rootfs),'/',
                                                       '--ro-bind',str(execution),'/experiment',
                                                       '--ro-bind',str(inputdir),'/tmp/inputs',
                                                       '--ro-bind',str(library),'/tmp/resource-archive.py',
                                                       '--bind',str(native_output),'/outputs',
                                                       '--','python',script,*argv]
  command,worker_argv=wrapped_command(original,code,worker_output)
  if not (native_output/'live.log').exists():
   (native_output/'live.log').write_text('live '+label+'\n')
  host={'command':command,'exit_code':0,'timed_out':False,'peak_rss_kib':1,'elapsed_seconds':0.01,
        'measurement':MEASUREMENT,
        'kernel_scope':{'path':'/sys/fs/cgroup/sureal-sustained-fixture.scope','memory_max_bytes':16*1024**3,
                        'memory_swap_max_bytes':0,'oom':0,'oom_kill':0,'members_verified':True,'process_ids':[123]},
        'stage_lifecycle':{'caller_pid':123,'scope_members_before':[123],'scope_members_after':[123],
                           'remaining_children':[],'subreaper_verified':True}}
  worker={'worker_argv':worker_argv,'measurement':'in-runtime getrusage SELF and waited CHILDREN KiB',
          'worker_pid':456,'exit_code':0,'self_peak_rss_kib':1,'waited_child_peak_rss_kib':0,
          'peak_rss_kib':1,'elapsed_seconds':0.01,
          'child_lifecycle':{'subreaper_verified':True,'remaining_children':[]}}
  worker_path=worker_output/'worker-resource.json';worker_path.write_text(json.dumps(worker,sort_keys=True))
  retained_log=proof_dir/'execution.log';retained_log.write_text((native_output/'live.log').read_text())
  proof={'schema_version':1,'admitted':True,'original_command':original,'command':command,
         'source_pins':pins,'native_output_directory':str(native_output),'cap_bytes':16*1024**3,
         'timeout_seconds':timeout,'worker_argv':worker_argv,'host_measurement':host,
         'worker_measurement':worker,
         'artifacts':{'worker_resource':{'path':str(worker_path),'sha256':sha(worker_path)},
                      'execution_log':{'path':str(retained_log),'sha256':sha(retained_log),
                                       'native_path':str(native_output/'live.log')}}}
  proof['resource_admission']=admit_worker(host,worker,command,worker_argv,16*1024**3)
  validate_proof(proof,command,Path(pins['source_snapshot_root']),pins,native_output,16*1024**3,timeout)
  proof_path=proof_dir/'resource-admitted.json';proof_path.write_text(json.dumps(proof,sort_keys=True))
  return proof_path,command

 def live_archive_check(self,root,pubroot,code,pins,execution,library,chunk,mode,index,validation):
  inputs=pubroot/str(index)/mode;inputs.mkdir(parents=True)
  job={'source_sha256':{m['path']:m['sha256'] for m in chunk['manifest']['members']},
       'max_bytes':LIMIT,'archive_module_path':'/tmp/resource-archive.py','archive_module_sha256':sha(library)}
  if mode!='create':job['manifest_sha256']=chunk['manifest_sha256']
  job_path=inputs/'job.json';job_path.write_text(json.dumps(job,sort_keys=True))
  native=pubroot/'native'/f'{index}-{mode}';proof,command=self.resource_proof(root,code,pins,native,inputs,'/experiment/resources/archive_worker.py',f'{index}-{mode}-live',(mode,),execution=execution,library=library)
  (native/'check.json').write_text(json.dumps(validation,sort_keys=True))
  retained=pubroot/f'{index}-{mode}-retained';retained.mkdir()
  for filename in ['check.json','live.log']:(retained/filename).write_text((native/filename).read_text())
  return {'stage':{'create':'create-live','verify':'verify-live','rehydrate':'rehydrate-live'}[mode],
          'command':command,'exit_code':0,'resource_proof_path':str(proof),'resource_proof_sha256':sha(proof),
          'input_directory':str(inputs),'input_hashes':{str(job_path):sha(job_path)},'validation':validation,
          'artifacts':{str(p):sha(p) for p in retained.iterdir()}}

 def independent_admission(self,root,pubroot,code,pins,pub,expected,readback):
  inputs=pubroot/'audit-input';inputs.mkdir()
  publication_for_audit={key:value for key,value in pub.items() if key!='independent_admission'}
  for name,value in [('publication.json',publication_for_audit),('expected.json',expected),('readback.json',readback)]:
   (inputs/name).write_text(json.dumps(value,sort_keys=True))
  native=pubroot/'native-independent'
  readonly=pub['audit_runtime_namespace']['readonly_entry_bindings']
  source_payload=pubroot/'raw-source'
  source_payload.mkdir()
  for name,entry in expected.items():
   target=source_payload/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(Path(entry['path']).read_bytes())
  original=launch_plan(Path(pub['rootfs_path']),Path(pub['execution_directory']),source_payload,native,
                       ['python','/experiment/resources/retention_audit.py'])
  index=original.index('--ro-bind')
  original[index:index+3]=readonly
  at=original.index('--')
  original[at:at]=['--ro-bind',str(inputs),'/tmp/inputs',
                   '--ro-bind',pub['archive_library']['path'],'/tmp/resource-archive.py']
  proof,command=self.resource_proof(root,code,pins,native,inputs,'/experiment/resources/retention_audit.py','independent',execution=Path(pub['execution_directory']),library=Path(pub['archive_library']['path']),command=original)
  validation=validate_union(pub,expected,readback);validation['corrupt_resource_copies_refused']=5
  (native/'check.json').write_text(json.dumps(validation,sort_keys=True))
  retained=pubroot/'independent';retained.mkdir()
  for filename in ['check.json','live.log']:(retained/filename).write_text((native/filename).read_text())
  return {'stage':'independent','command':command,'exit_code':0,'resource_proof_path':str(proof),
          'resource_proof_sha256':sha(proof),'input_directory':str(inputs),
          'input_hashes':{str(p):sha(p) for p in sorted(inputs.iterdir())},
          'validation':validation,'artifacts':{str(p):sha(p) for p in retained.iterdir()}}

 def resource_receipt(self,root,backend,record,inventory,*,independent=True,readback=True):
  pubroot=root/'resource-pub';pubroot.mkdir()
  source=Path(__file__).resolve().parents[1]/'resources'
  identity=getattr(backend,'_resource_identity',None)
  if identity is not None and identity.get('source_pins'):
   pins=identity['source_pins'];code=validate_resource_sources(source,pins);execution=root/'execution'
   library=source/'resource_archive.py';materialize_execution_package(code,execution,library,sha(library),pins)
  else:
   source,pins,code,execution,library=self.resource_source_fixture(root);backend._resource_identity={'source_pins':pins}
  if not (hasattr(backend,'host_pins') and 'resources/resource_archive.py' in backend.host_pins.get('source_pins',{})):
   backend.host_pins={'source_snapshot_root':str(source.parent),'source_pins':{'resources/resource_archive.py':sha(source/'resource_archive.py')}}
  library=Path(backend.host_pins['source_snapshot_root'])/'resources/resource_archive.py'
  if not hasattr(backend,'cpu_runtime'):backend.cpu_runtime={'rootfs_sha256':'f'*64,'image_id':'cpu-fixture'}
  if not hasattr(backend,'resource_cpu_root'):
   backend.resource_cpu_root=root/'rootfs';backend.resource_cpu_root.mkdir(exist_ok=True)
  for name in ['bin','usr','lib','experiment','source','outputs','dev','proc','tmp']:
   (backend.resource_cpu_root/name).mkdir(exist_ok=True)
  expected=pubroot/'expected.json';expected.write_text(json.dumps(inventory,sort_keys=True))
  archive='a'*64;members=[{'path':name,'sha256':entry['sha256'],'bytes':entry['bytes']} for name,entry in sorted(inventory.items())]
  payload=sum(member['bytes'] for member in members)
  validation={'archive_sha256':archive,'exact_members_and_hashes':True,'members':len(members),'payload_bytes':payload}
  prefix='hdfs://harunava/user/tiger/waystone/sureal/runs/perception-resource-closures/balanced16-fixture'
  manifest={'members':members,'payload_bytes':payload,'archive_sha256':archive}
  manifest_path=pubroot/'0/manifest.json';readback_manifest=pubroot/'0/readback.json';manifest_path.parent.mkdir()
  manifest_path.write_text(json.dumps(manifest,sort_keys=True));readback_manifest.write_text(json.dumps(manifest,sort_keys=True))
  chunk={'manifest':manifest,'manifest_sha256':sha(manifest_path),'manifest_path':str(manifest_path),'readback_path':str(readback_manifest),'archive_hdfs_uri':prefix+'/'+archive+'/archive.tar.gz','manifest_hdfs_uri':prefix+'/'+archive+'/manifest.json','checks':[]}
  chunk['checks'].append(self.live_archive_check(root,pubroot,code,pins,execution,library,chunk,'create',0,validation))
  for stage in ['archive-put','archive-get','manifest-put','manifest-get']:
   log=pubroot/(stage+'.log');log.write_text(stage+'\n');chunk['checks'].append({'stage':stage,'command':['waystone',stage],'exit_code':0,'log_path':str(log),'log_sha256':sha(log)})
  chunk['checks'].append(self.live_archive_check(root,pubroot,code,pins,execution,library,chunk,'verify',0,validation))
  chunk['checks'].append(self.live_archive_check(root,pubroot,code,pins,execution,library,chunk,'rehydrate',0,{**validation,'verified_rehydration':True}))
  masked={'experiment','source','outputs','dev','proc','tmp'}
  entries=sorted(backend.resource_cpu_root.iterdir(),key=lambda p:p.name)
  readonly=[item for path in entries if path.name not in masked for item in ['--ro-bind',str(path),'/'+path.name]]
  namespace={'private_tmpfs_root':True,'source_rootfs_sha256':backend.cpu_runtime['rootfs_sha256'],
             'readonly_entry_bindings':readonly,
             'masked_role_entries':[p.name for p in entries if p.name in masked],
             'source_entry_types':{p.name:{'kind':'directory','symlink_target':None} for p in entries},
             'scope':'readonly rootfs source entries over a private root; symlink source entries dereference to mounts; native roles override their original stubs'}
  base={'schema_version':1,'kind':'checkpoint','hdfs_prefix':prefix,'source_inventory':inventory,'source_inventory_sha256':sha(expected),'resource_identity_sha256':backend.resource_identity_sha256,'native_manifest_sha256':backend.manifest_sha,'resource_source_pins':pins,'resource_source_directory':str(source),'execution_directory':str(execution),'runtime_lock':backend.cpu_runtime,'rootfs_path':str(backend.resource_cpu_root),'audit_runtime_namespace':namespace,'archive_library':{'path':str(library),'sha256':sha(library)},'chunks':[chunk]}
  readback_value={**base}
  readback_path=pubroot/'publication-readback.json';readback_path.write_text(json.dumps(readback_value,sort_keys=True))
  pub={**base,'manifest_readback_exact':True,'publication_manifest_hdfs_uri':prefix+'/publication-manifest.json','publication_manifest_sha256':sha(readback_path)}
  pub['independent_admission']=self.independent_admission(root,pubroot,code,pins,pub,inventory,readback_value)
  if not independent:
   pub['independent_admission']={**pub['independent_admission'],'exit_code':1,'validation':{**pub['independent_admission']['validation'],'whole_member_union_exact':False}}
  if not readback:
   readback_path.write_text(json.dumps({**readback_value,'kind':'shared'},sort_keys=True))
   pub['publication_manifest_sha256']=sha(readback_path)
  receipt=pubroot/'verified-publication.json';receipt.write_text(json.dumps(pub,sort_keys=True))
  return {'path':str(receipt),'sha256':sha(receipt),'hdfs_manifest_uri':pub['publication_manifest_hdfs_uri'],'kind':'checkpoint'}

 def native_stage_command(self,backend,requested,output,entry):
  inputs=backend.R/(requested+'-input');inputs.mkdir()
  (inputs/'manifest.json').write_text((backend.source/'manifest.json').read_text())
  return (inputs,['bwrap','--unshare-all','--die-with-parent',
                  '--ro-bind',str(backend.package),'/experiment',
                  '--bind',str(output),'/outputs',
                  '--ro-bind',str(backend.R/'source-snapshots'),'/tmp/source-snapshots',
                  '--setenv','SUREAL_SOURCE_SNAPSHOT_STORE','/tmp/source-snapshots',
                  '--ro-bind',str(inputs),'/source',
                  '--ro-bind',str(inputs),'/tmp/inputs',
                  '--','python',entry])

 def add_resource_binding(self,root,backend,receipt_path,receipt):
  evidence=backend.resource_root/'stages'/receipt['requested_stage'];evidence.mkdir(parents=True)
  resource_source=Path(__file__).resolve().parents[1]/'resources'
  source=validate_resource_sources(resource_source,backend.resource_identity['source_pins'])
  native=Path(receipt['output_directory'])
  metric=receipt['stage'].rsplit('-',1)[0] in {'score','metrics-audit'}
  timeout=backend.resource_stage_timeout(metric)
  proof,command=self.resource_proof(root,source,backend.resource_identity['source_pins'],native,evidence,'/experiment/resources/execute_worker.py',receipt['requested_stage'],execution=source,library=Path(__file__).resolve().parents[1]/'resources/resource_archive.py',command=receipt['command'],timeout=timeout,evidence_dir=evidence)
  receipt['command']=command;receipt_path.write_text(json.dumps(receipt,sort_keys=True))
  proof_target=evidence/'resource-admitted.json';value=json.loads(proof_target.read_text())
  from resources.backend import CAP_BYTES
  from resources.stage import validate_proof
  validate_proof(value,receipt['command'],resource_source,backend.resource_identity['source_pins'],native,CAP_BYTES,timeout)
  backend.bind_completed_stage(receipt_path)

 def full_resume_backend_and_record(self,root):
  from resources.backend import prepare_identity
  from resources.checkpoint import resource_inventory, seal_checkpoint, write_publication_record
  from evidence.source_snapshot import LocalSnapshotStore, copy_source_snapshot, source_snapshot_receipt
  from training_execution.sustained_admission import admit_sample
  backend=self.backend(root);backend.output=root/'case-output';backend.output.mkdir();backend.source=backend.R/'input';backend.source.mkdir();backend.package=backend.R/'code';backend.package.mkdir();backend.verifier=backend.R/'verifier';backend.verifier.mkdir();(backend.R/'source-snapshots').mkdir()
  backend.runtime={'rootfs_sha256':'a'*64,'image_id':'gpu'};backend.cpu_runtime={'rootfs_sha256':'b'*64,'image_id':'cpu'};backend.metric_runtime={'rootfs_sha256':'c'*64,'image_id':'metrics'};backend.old={'driver_hashes':{}}
  package_file=backend.package/'training_execution/fixture.py';package_file.parent.mkdir(parents=True);package_file.write_text('fixture=1\n')
  backend.pins=source_snapshot_receipt(backend.package,['training_execution/fixture.py'],LocalSnapshotStore(backend.R/'native-package-snapshots'),target='fixture:native-package',materialized_root=backend.package)
  host=root/'host-source';archive=host/'resources/resource_archive.py';archive.parent.mkdir(parents=True);archive.write_text((Path(__file__).resolve().parents[1]/'resources/resource_archive.py').read_text())
  backend.host_pins=copy_source_snapshot(host,['resources/resource_archive.py'],backend.R/'host-source',LocalSnapshotStore(backend.R/'host-source-snapshots'),target='fixture:host')
  backend.verifier_pins={};backend.anchor_sha='e'*64
  frames=[{'identity':str(i)} for i in range(16)];backend.manifest={'frames':frames,'recipe':'baseline'};(backend.source/'manifest.json').write_text(json.dumps(backend.manifest,sort_keys=True));backend.manifest_sha=sha(backend.source/'manifest.json')
  (backend.R/'run.json').write_text(json.dumps({'run':'fixture'},sort_keys=True))
  backend.runtime_path=backend.R/'runtime-lock.json';backend.runtime_path.write_text(json.dumps(backend.runtime,sort_keys=True))
  repo,runner=self.resource_snapshot_query()
  path,digest=prepare_identity(backend,backend.R/'resource-layer-full',source_snapshot_store=LocalSnapshotStore(backend.R/'resource-source-snapshots'),repo_root=repo,bazel=repo/'bazelw',runner=runner);backend.attach_resources(path,digest)
  step=1000;target=1000;payload=backend.output/f'update-{target:02d}';(payload/'heads').mkdir(parents=True)
  (payload/'checkpoint.pt').write_text('checkpoint\n');(payload/'live.log').write_text('train log\n')
  heads={}
  for index in range(16):
   head=payload/'heads'/f'heads-{index:02d}.npz';head.write_text(f'head {index}\n');heads[head.name]=sha(head)
  producer={'updates':step,'requested_updates':target,'head_hashes':heads,'checkpoint_sha256':sha(payload/'checkpoint.pt'),'resource_gate_passed':True,'manifest_sha256':backend.manifest_sha,'peak_allocated_bytes':0,'peak_rss_kib':1,'stop_reason':'sample','cumulative_train_seconds':1}
  (payload/'check.json').write_text(json.dumps(producer,sort_keys=True));reportcopy=backend.R/f'producer-report-{target:02d}.json';reportcopy.write_text(json.dumps(producer,sort_keys=True))
  common={'manifest_sha256':backend.manifest_sha,'checkpoint_sha256':producer['checkpoint_sha256']}
  reports={
   'audit':{'replay.json':{**common,'updates':step,'head_hashes':heads,'checked_frames':[f['identity'] for f in frames]},'transition.json':{**common,'previous_checkpoint_sha256':None,'start_step':0,'terminal_step':step,'literal_updates':step,'state_exact_excluding_training_seconds':True,'producer_synchronized_seconds_reconciled':True,'peak_allocated_bytes':0,'peak_rss_kib':1}},
   'literal-loss':{'check.json':{'manifest_sha256':backend.manifest_sha,'report_sha256':sha(reportcopy),'frames':16,'recipe':'baseline','updates':step,'head_hashes':heads,'rows':[{'identity':f['identity']} for f in frames]}},
   'proposals':{'check.json':{'frames':16,'literal_score_first_decode_nms_and_measurement_metadata':True,'all_native_GT_retained':True,'native_groundtruth':{'ok':True},'predictions':{'ok':True}}},
   'score':{'check.json':{'decoder_version':3,'groundtruth_policy':'all native four-class boxes; native evaluator handles eligibility','manifest_sha256':backend.manifest_sha,'head_hashes':heads,'frames':[{'identity':f['identity']} for f in frames],'native_groundtruth':{'ok':True},'predictions':{'ok':True},'LEVEL2_per_class':{str(i):{'AP':0.9,'APH':0.9} for i in range(1,5)},'all_class_APH_gate_passed':True,'APH_gate_passed':True}},
   'metrics-audit':{'check.json':{'all_export_fields_independently_reread':True,'native_metric_replay_exact':True,'all_class_APH_gate_passed':True}},
  }
  stage_entries={'train':'/experiment/training_execution/train_sustained.py','audit':'/tmp/verifier/audit_sustained_transition.py','literal-loss':'/experiment/training_execution/audit_sustained_loss.py','export':'/experiment/evaluation/prepare_sustained_v3.py','proposals':'/experiment/evaluation/audit_proposals_sustained_v3.py','score':'/experiment/evaluation/metrics_sustained_v3.py','metrics-audit':'/experiment/evaluation/audit_metrics_sustained_v3.py'}
  output_names={'train':payload,'audit':backend.R/f'audit-{target:02d}','literal-loss':backend.R/f'loss-{target:02d}','export':backend.R/f'prepared-{target:02d}','proposals':backend.R/f'proposal-audit-{target:02d}','score':backend.R/f'scored-{target:02d}','metrics-audit':backend.R/f'metric-audit-{target:02d}'}
  refs={}
  for name,out in output_names.items():
   out.mkdir(exist_ok=True)
   if name!='train':(out/'live.log').write_text(name+' log\n')
   for filename,value in reports.get(name,{}).items():(out/filename).write_text(json.dumps(value,sort_keys=True))
   requested=f'{name}-{target}';inputs,command=self.native_stage_command(backend,requested,out,stage_entries[name])
   artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file()}
   receipt={'stage':f'{name}-{step}','requested_stage':requested,'command':command,'output_directory':str(out),'exit_code':0,'source_hashes':backend.pins,'runtime_lock':backend.metric_runtime if name in {'score','metrics-audit'} else backend.runtime if name in {'train','audit'} else backend.cpu_runtime,'driver_hashes':{} ,'verifier_source_pins':{},'manifest_sha256':backend.manifest_sha,'input_hashes':{str(inputs/'manifest.json'):backend.manifest_sha},'artifacts':artifacts,'scope':'fixture'}
   path=backend.R/(requested+'-verified.json');path.write_text(json.dumps(receipt,sort_keys=True));self.add_resource_binding(root,backend,path,receipt);refs[name]={'path':str(path),'sha256':sha(path)}
  final=backend.R/f'checkpoint-{target:02d}-admitted.json';final.write_text(json.dumps({'output_directory':str(payload),'manifest_path':str(backend.source/'manifest.json'),'manifest_sha256':backend.manifest_sha,'step':step,'stage_receipts':refs,'scope':'fixture'},sort_keys=True))
  sample=admit_sample(manifest=backend.manifest,manifest_sha256=backend.manifest_sha,producer=producer,producer_sha256=sha(reportcopy),replay=reports['audit']['replay.json'],transition=reports['audit']['transition.json'],previous_checkpoint_sha256=None,start_step=0,loss=reports['literal-loss']['check.json'],proposals=reports['proposals']['check.json'],score=reports['score']['check.json'],metric=reports['metrics-audit']['check.json'])
  record={'step':step,'target_step':target,'root':str(payload),'checkpoint_sha256':producer['checkpoint_sha256'],'final_path':str(final),'final_sha256':sha(final),'report':producer,'report_snapshot':str(reportcopy),'report_sha256':sha(reportcopy),'sample':sample,'released':False}
  seal_checkpoint(backend,record);inventory=resource_inventory(backend,record);receipt=self.resource_receipt(root,backend,record,inventory);write_publication_record(backend,record,receipt,inventory);record.pop('resource_publication')
  return backend,record,inventory,receipt

 def write_native_release(self,cache,record,*,completed=True,release_plan=None):
  release_dir=cache/'insula/hdfs-retention-fixture';release_dir.mkdir(parents=True,exist_ok=True)
  full_plan=[{'path':str(p.relative_to(record['root'])),'local_path':str(p),'sha256':sha(p),'bytes':p.stat().st_size,'archive_hdfs_uri':'hdfs://native/archive.tar.gz'} for p in sorted(Path(record['root']).rglob('*')) if p.is_file()]
  if release_plan is None:
   release_plan=full_plan
  source={entry['path']:entry['sha256'] for entry in full_plan}
  manifest={'members':[{key:entry[key] for key in ['path','sha256','bytes']} for entry in full_plan],
            'payload_bytes':sum(entry['bytes'] for entry in full_plan),'archive_sha256':'a'*64}
  publication=release_dir/'verified-publication.json';publication.write_text(json.dumps({'parent_receipts':{record['final_path']:record['final_sha256']},'source_sha256':source,'chunks':[{'archive_hdfs_uri':'hdfs://native/archive.tar.gz','manifest':manifest}],'independent_admission':{'exit_code':0,'validation':{'whole_member_union_exact':True}},'publication_manifest_hdfs_uri':'hdfs://native/manifest','release_plan':release_plan},sort_keys=True))
  release=release_dir/'release-completed.json'
  if completed:release.write_text(json.dumps({'publication_receipt_sha256':sha(publication),'released':release_plan},sort_keys=True))
  return publication,release,release_plan

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

 def tamper_resource_receipt(self,receipt,fault):
  publication=Path(receipt['path']);pub=json.loads(publication.read_text())
  if fault=='chunk_proof':
   Path(pub['chunks'][0]['checks'][0]['resource_proof_path']).write_text('{}')
  elif fault=='independent_proof':
   Path(pub['independent_admission']['resource_proof_path']).unlink()
  elif fault=='independent_output':
   artifacts=pub['independent_admission']['artifacts'];check=[Path(p) for p in artifacts if Path(p).name=='check.json'][0];check.write_text('{}')
  elif fault=='independent_log':
   artifacts=pub['independent_admission']['artifacts'];log=[Path(p) for p in artifacts if Path(p).name=='live.log'][0];log.write_text('tampered log\n')
  elif fault=='independent_input':
   (Path(pub['independent_admission']['input_directory'])/'expected.json').write_text('{}')
  elif fault=='source':
   source=Path(pub['resource_source_pins']['source_snapshot_root'])/'autonomy/resources/stage.py';source.chmod(0o644);source.write_text(source.read_text()+'\n# tampered\n')
  elif fault=='missing_command':
   del pub['independent_admission']['command'];publication.write_text(json.dumps(pub,sort_keys=True));receipt['sha256']=sha(publication)
  else:
   raise AssertionError(fault)

 def rewrite_publication(self,receipt,pub,*,readback=True):
  publication=Path(receipt['path']);pubroot=publication.parent
  if readback:
   value={key:value for key,value in pub.items() if key not in {'manifest_readback_exact','publication_manifest_hdfs_uri','publication_manifest_sha256','independent_admission'}}
   readback_path=pubroot/'publication-readback.json';readback_path.write_text(json.dumps(value,sort_keys=True));pub['publication_manifest_sha256']=sha(readback_path)
  publication.write_text(json.dumps(pub,sort_keys=True));receipt['sha256']=sha(publication)

 def replace_independent_proof(self,root,receipt,worker,*,input_mount=None,overlay_alias=None,late_tmpfs=False):
  publication=Path(receipt['path']);pub=json.loads(publication.read_text());admission=pub['independent_admission']
  inputs=Path(admission['input_directory']);mounted=inputs if input_mount is None else Path(input_mount)
  native=publication.parent/('native-'+worker.replace('/','-'));readonly=pub['audit_runtime_namespace']['readonly_entry_bindings']
  source_payload=publication.parent/'raw-source'
  original=launch_plan(Path(pub['rootfs_path']),Path(pub['execution_directory']),source_payload,native,
                       ['python',worker])
  index=original.index('--ro-bind')
  original[index:index+3]=readonly
  at=original.index('--')
  original[at:at]=['--ro-bind',str(mounted),'/tmp/inputs',
                   '--ro-bind',pub['archive_library']['path'],'/tmp/resource-archive.py']
  if overlay_alias is not None:
   overlay=root/'overlay';overlay.mkdir()
   original[original.index('--'):original.index('--')]=['--bind',str(overlay),overlay_alias]
  if late_tmpfs:
   temporary=original.index('--tmpfs');self.assertEqual(original[temporary+1],'/tmp')
   del original[temporary:temporary+2]
   original[original.index('--'):original.index('--')]=['--tmpfs','/tmp']
  resource_source=Path(pub['resource_source_directory'])
  proof,command=self.resource_proof(root,validate_resource_sources(resource_source,pub['resource_source_pins']),pub['resource_source_pins'],native,mounted,worker,'substitution',command=original,execution=Path(pub['execution_directory']),library=Path(pub['archive_library']['path']))
  admission['resource_proof_path']=str(proof);admission['resource_proof_sha256']=sha(proof);admission['command']=command
  log=[Path(path) for path in admission['artifacts'] if Path(path).name=='live.log'][0]
  log.write_text((native/'live.log').read_text());admission['artifacts'][str(log)]=sha(log)
  self.rewrite_publication(receipt,pub,readback=False)

 def test_coherent_independent_worker_or_mount_substitution_refused(self):
  cases=['wrong_worker','wrong_input_mount','protected_alias_overlay','protected_alias_descendant_overlay','protected_alias_ancestor_overlay']
  for case in cases:
   with self.subTest(case=case),tempfile.TemporaryDirectory() as temp:
    root=Path(temp);backend=self.backend(root);record=self.record(root);inventory=self.inventory(root,record);receipt=self.resource_receipt(root,backend,record,inventory)
    if case=='wrong_worker':
     self.replace_independent_proof(root,receipt,'/experiment/resources/archive_worker.py')
    else:
     if case in {'protected_alias_overlay','protected_alias_descendant_overlay','protected_alias_ancestor_overlay'}:
      alias={'protected_alias_overlay':'/tmp/inputs','protected_alias_descendant_overlay':'/tmp/inputs/publication.json','protected_alias_ancestor_overlay':'/tmp'}[case]
      self.replace_independent_proof(root,receipt,'/experiment/resources/retention_audit.py',overlay_alias=alias)
      with patch('training_execution.run_sustained.resource_inventory',return_value=inventory),patch('training_execution.run_sustained.publish_bundle',return_value=receipt),patch('training_execution.run_sustained.NativeBackend.publish_and_release') as native:
       with self.assertRaisesRegex(ValueError,'independent resource audit command mounts differ'):backend.publish_and_release(record)
      native.assert_not_called()
      continue
     alternate=root/'alternate-audit-input';alternate.mkdir()
     for source in Path(json.loads(Path(receipt['path']).read_text())['independent_admission']['input_directory']).iterdir():
      (alternate/source.name).write_text(source.read_text())
     self.replace_independent_proof(root,receipt,'/experiment/resources/retention_audit.py',input_mount=alternate)
    with patch('training_execution.run_sustained.resource_inventory',return_value=inventory),patch('training_execution.run_sustained.publish_bundle',return_value=receipt),patch('training_execution.run_sustained.NativeBackend.publish_and_release') as native:
     with self.assertRaises(ValueError):backend.publish_and_release(record)
    native.assert_not_called()

 def test_tmpfs_mount_must_precede_audit_inputs(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);backend=self.backend(root);record=self.record(root);inventory=self.inventory(root,record);receipt=self.resource_receipt(root,backend,record,inventory)
   self.replace_independent_proof(root,receipt,'/experiment/resources/retention_audit.py',late_tmpfs=True)
   with patch('training_execution.run_sustained.resource_inventory',return_value=inventory),patch('training_execution.run_sustained.publish_bundle',return_value=receipt),patch('training_execution.run_sustained.NativeBackend.publish_and_release') as native:
    with self.assertRaisesRegex(ValueError,'independent resource audit command mounts differ'):backend.publish_and_release(record)
   native.assert_not_called()

 def test_coherent_foreign_source_runtime_or_log_substitution_refused(self):
  cases=['foreign_source','foreign_runtime','rehash_log']
  for case in cases:
   with self.subTest(case=case),tempfile.TemporaryDirectory() as temp:
    root=Path(temp);backend=self.backend(root);record=self.record(root);inventory=self.inventory(root,record);receipt=self.resource_receipt(root,backend,record,inventory);publication=Path(receipt['path']);pub=json.loads(publication.read_text())
    if case=='foreign_source':
     source,pins,code,execution,library=self.resource_source_fixture(root/'foreign')
     pub['resource_source_pins']=pins;pub['resource_source_directory']=str(source);pub['execution_directory']=str(execution)
     self.rewrite_publication(receipt,pub)
    elif case=='foreign_runtime':
     pub['runtime_lock']={'rootfs_sha256':'9'*64,'image_id':'foreign'};foreign=root/'foreign-rootfs';foreign.mkdir();pub['rootfs_path']=str(foreign)
     self.rewrite_publication(receipt,pub)
    else:
     artifacts=pub['independent_admission']['artifacts'];log=[Path(p) for p in artifacts if Path(p).name=='live.log'][0]
     log.write_text('coherently replaced retained audit log\n');pub['independent_admission']['artifacts'][str(log)]=sha(log)
     self.rewrite_publication(receipt,pub,readback=False)
    with patch('training_execution.run_sustained.resource_inventory',return_value=inventory),patch('training_execution.run_sustained.publish_bundle',return_value=receipt),patch('training_execution.run_sustained.NativeBackend.publish_and_release') as native:
     with self.assertRaises(ValueError):backend.publish_and_release(record)
    native.assert_not_called()

 def test_retained_resource_evidence_faults_block_native_release(self):
  faults=['chunk_proof','independent_proof','independent_output','independent_log','independent_input','source','missing_command']
  for fault in faults:
   with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
    root=Path(temp);backend=self.backend(root);record=self.record(root);inventory=self.inventory(root,record)
    receipt=self.resource_receipt(root,backend,record,inventory);self.tamper_resource_receipt(receipt,fault)
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
   root=Path(temp);backend,record,inventory,receipt=self.full_resume_backend_and_record(root)
   cache=root/'cache';publication,release,plan=self.write_native_release(cache,record)
   for member in plan:Path(member['local_path']).unlink()
   self.assertTrue(Path(record['root']).exists());self.assertTrue((Path(record['root'])/'heads').exists())
   with patch('training_execution.run_sustained.C',cache):
    backend.check_record(record,None)
   self.assertTrue(record['released']);self.assertIn('resource_publication',record);self.assertEqual(record['publication']['publication_sha256'],sha(publication))

 def test_check_record_refuses_partial_native_release_without_completion(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);backend,record,inventory,receipt=self.full_resume_backend_and_record(root)
   cache=root/'cache';publication,release,plan=self.write_native_release(cache,record,completed=False)
   Path(plan[0]['local_path']).unlink()
   with patch('training_execution.run_sustained.C',cache):
    with self.assertRaises(ValueError):backend.check_record(record,None)

 def test_check_record_refuses_tampered_completed_native_release(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);backend,record,inventory,receipt=self.full_resume_backend_and_record(root)
   cache=root/'cache';publication,release,plan=self.write_native_release(cache,record)
   for member in plan[1:]:Path(member['local_path']).unlink()
   with patch('training_execution.run_sustained.C',cache):
    with self.assertRaises(ValueError):backend.check_record(record,None)

 def test_check_record_refuses_reduced_release_plan_after_payload_deletion(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);backend,record,inventory,receipt=self.full_resume_backend_and_record(root)
   cache=root/'cache';publication,release,plan=self.write_native_release(cache,record)
   reduced=plan[:-1]
   manifest={'members':[{key:entry[key] for key in ['path','sha256','bytes']} for entry in reduced],
             'payload_bytes':sum(entry['bytes'] for entry in reduced),'archive_sha256':'b'*64}
   publication.write_text(json.dumps({'parent_receipts':{record['final_path']:record['final_sha256']},'source_sha256':{entry['path']:entry['sha256'] for entry in reduced},'chunks':[{'archive_hdfs_uri':'hdfs://native/reduced/archive.tar.gz','manifest':manifest}],'independent_admission':{'exit_code':0,'validation':{'whole_member_union_exact':True}},'publication_manifest_hdfs_uri':'hdfs://native/manifest','release_plan':reduced},sort_keys=True))
   release.write_text(json.dumps({'publication_receipt_sha256':sha(publication),'released':reduced},sort_keys=True))
   for member in plan:Path(member['local_path']).unlink()
   with patch('training_execution.run_sustained.C',cache):
    with self.assertRaises(ValueError):backend.check_record(record,None)


if __name__=='__main__':unittest.main()
