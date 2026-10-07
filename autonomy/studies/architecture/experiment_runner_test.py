import ast,hashlib,importlib.util,io,json,os,subprocess,sys,tarfile,tempfile,types,unittest
from pathlib import Path
from evidence.source_snapshot import materialize_receipt_sources
p=Path(__file__).with_name('experiment_runner.py');spec=importlib.util.spec_from_file_location('experiment_runner',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class RunnerTests(unittest.TestCase):
 def write_runner_fixture(self,repo):
  package_root=repo/'autonomy';here=package_root/'studies/architecture'
  for path in [package_root/'pipeline',package_root/'detection',package_root/'research',here/'harness',repo/'docs/superpowers/specs']:
   path.mkdir(parents=True)
  (package_root/'pipeline/module.py').write_text('pass\n')
  (package_root/'detection/worker.py').write_text('pass\n')
  (package_root/'research/overfit-native-cache-progress.json').write_text('{"admitted_frames":16,"selected_frames":16,"frame_evidence":{}}\n')
  (package_root/'research/unrelated-retained-evidence.json').write_text('not a run input\n')
  (repo/'docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md').write_text('# spec\n')
  (here/'registry.json').write_text(json.dumps({'residual_bev':{'status':'runnable','title':'Residual BEV'}}))
  drivers=[stage['driver'] for stage in module.stages_for('residual_bev')]
  (here/'harness/files.json').write_text(json.dumps(drivers))
  for driver in drivers:
   (here/'harness'/driver).write_text('pass\n')
  return package_root,here
 def archive(self,files):
  payload=io.BytesIO();pins={}
  with tarfile.open(fileobj=payload,mode='w',format=tarfile.PAX_FORMAT) as writer:
   for name,data in sorted(files.items()):
    raw=data.encode()
    pins[name]=hashlib.sha256(raw).hexdigest()
    info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o444;info.mtime=0;info.uid=0;info.gid=0;info.uname='';info.gname='';info.pax_headers={}
    writer.addfile(info,io.BytesIO(raw))
  archive=payload.getvalue()
  return archive,hashlib.sha256(archive).hexdigest(),pins
 def query_runner(self,names):
  def run(command,**kwargs):
   self.assertIn('query',command)
   class Result:pass
   result=Result()
   result.stdout=''.join('//'+name.rsplit('/',1)[0]+':'+name.rsplit('/',1)[1]+'\n' for name in sorted(names))
   return result
  return run
 def patch_module_paths(self,here,package,repo):
  old_here,old_package,old_repo=module.HERE,module.PACKAGE,module.REPO
  module.HERE,module.PACKAGE,module.REPO=here,package,repo
  return old_here,old_package,old_repo
 def restore_module_paths(self,old):
  module.HERE,module.PACKAGE,module.REPO=old
 def test_unique_label_and_reject_traversal(self):
  self.assertEqual(module.run_label('residual_bev','trial-01'),'residual_bev--trial-01')
  for bad in ['../escape','a/b','', '.', 'white space']:
   with self.assertRaises(ValueError):module.run_label('residual_bev',bad)
 def test_planned_idea_has_no_execution_plan(self):
  with self.assertRaises(ValueError):module.stages_for('ragged_pillars')
 def test_all_eight_have_full_native_gates(self):
  for name in ['deep_pfn','context_pfn','residual_bev','retain64','masked_pfn','window_bev','coarse_mlp','all_pillars']:
   stages=module.stages_for(name);self.assertEqual([s['name'] for s in stages][-5:],['train','checkpoint','loss','score','score_audit'])
 def test_verify_rejects_tampered_artifact(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'output';p.write_text('original');receipt={'artifacts':{str(p):module.sha(p)}};module.verify_receipt(receipt,Path(tmp));p.write_text('changed')
   with self.assertRaises(ValueError):module.verify_receipt(receipt,Path(tmp))
 def test_relative_worker_hashes_resolve_from_snapshot_scratch_after_rename(self):
  with tempfile.TemporaryDirectory() as tmp:
   source=Path(tmp)/'source';package=source/'autonomy';worker=source/'.scratch'/'worker.py'
   worker.parent.mkdir(parents=True);package.mkdir()
   worker.write_text('pass\n')
   receipt={'worker_hashes':{'worker.py':module.sha(worker)},'checks':[{'exit_code':0}]}
   module.verify_receipt(receipt,package)
 def test_worker_binding_is_not_confused_with_python_invocation(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'worker.py';p.write_text('worker')
   receipt={'artifacts':{},'worker_sha256':module.sha(p),'checks':[{'exit_code':0,'command':['--ro-bind',str(p),'/tmp/worker.py','--','python','/tmp/worker.py']}]}
   module.verify_receipt(receipt,Path(tmp))
 def test_source_worker_hashes_accept_detection_and_legacy_gpu_paths(self):
  with tempfile.TemporaryDirectory() as tmp:
   package=Path(tmp)/'autonomy';(package/'detection').mkdir(parents=True);(package/'gpu').mkdir()
   for area in ['detection','gpu']:
    worker=package/area/'worker.py';worker.write_text(area)
    receipt={'artifacts':{},'worker_sha256':module.sha(worker),'checks':[{'exit_code':0,'command':['python','/experiment/'+area+'/worker.py']}]}
    module.verify_receipt(receipt,package)
 def test_namespacing_changes_receipts_but_not_model_variant(self):
  source="variant=sys.argv[1];assert variant in ['residual_bev']\nevidence=code/('research/architecture-'+variant+'-execution-verified.json')\nmanifest={'architecture_variant':variant}\n"
  patched=module.parameterize_driver(source)
  self.assertIn("'architecture_variant':variant",patched)
  self.assertIn("'run_label':run_label",patched)
  self.assertIn("'research/architecture-'+run_label",patched)
 def test_parameterized_driver_uses_pinned_study_spec_digest(self):
  source="manifest={'spec_sha256':sha(Path('docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md'))}\n"
  patched=module.parameterize_driver(source)
  self.assertIn(repr(module.ARCHITECTURE_STUDY_SPEC_SHA256),patched)
  self.assertNotIn("docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md",patched)
 def test_audit_mount_selection_uses_path_component(self):
  for name in ['audit-architecture-score-first-proposals.py','audit-architecture-score-first-native-metrics.py']:
   tree=ast.parse((module.HERE/'harness'/name).read_text())
   node=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='directory' for t in n.targets))
   expression=compile(ast.Expression(node.value),'<actual-audit-selector>','eval')
   self.assertEqual(eval(expression,{'Path':Path,'path':'/cache/architecture--prepared-trial/scored/check.json'}),Path('/tmp/scored'))
   self.assertEqual(eval(expression,{'Path':Path,'path':'/cache/trial/prepared/check.json'}),Path('/source'))
 def test_manifest_tampering_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   directory=Path(tmp);p=directory/'manifest.json';p.write_text('{}')
   receipt={'artifacts':{},'manifest_sha256':module.sha(p),'checks':[{'exit_code':0,'command':['--ro-bind',str(directory),'/tmp/inputs']}]}
   module.verify_receipt(receipt,directory);p.write_text('{"changed":true}')
   with self.assertRaises(ValueError):module.verify_receipt(receipt,directory)
 def test_summary_requires_contracts(self):
  with tempfile.TemporaryDirectory() as tmp:
   package=Path(tmp);research=package/'research';research.mkdir();label='residual_bev--test'
   def save(suffix,data):
    p=research/f'architecture-{label}-{suffix}-verified.json';p.write_text(json.dumps(data));return module.sha(p)
   producer=save('execution',{'validation':{'parameters':1,'cumulative_train_seconds':0}})
   save('checkpoint-audit',{'producer_evidence_sha256':producer});save('loss-audit',{'producer_evidence_sha256':producer})
   score=save('score-first',{'training_evidence_sha256':producer,'validation':{'curve':[{'mean_populated_class_APH':.9,'LEVEL2_per_class':{'3':{'APH':.7}}}]*11,'first_observed_pass':{}}})
   save('score-first-audits',{'producer_evidence_sha256':score,'validation':[{}]*11})
   with self.assertRaises(ValueError):module.summarize(package,'residual_bev',label)
 def test_reserved_red_id_has_green_contract_label(self):
  self.assertNotEqual(module.contract_label('red'),'red')
 def test_timeout_cleans_up_descendant_process(self):
  with tempfile.TemporaryDirectory() as tmp:
   directory=Path(tmp);pidfile=directory/'child.pid'
   script="import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);Path("+repr(str(pidfile))+").write_text(str(p.pid));time.sleep(30)"
   with (directory/'log').open('w') as log:
    with self.assertRaises(subprocess.TimeoutExpired):module.run_stage([sys.executable,'-c',script],directory,dict(os.environ),log,timeout=.5)
   pid=int(pidfile.read_text());state=Path('/proc')/str(pid)/'stat'
   self.assertTrue(not state.exists() or state.read_text().split(') ',1)[1][0]=='Z')
 def test_snapshot_dependency_closure_and_no_scratch_dependency(self):
  module.check_harness_closure()
 def test_snapshot_packages_autonomy_at_top_level(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);repo=root/'repo';package_root,here=self.write_runner_fixture(repo)
   archive,digest,pins=self.archive({
    'autonomy/studies/architecture/harness/files.json':(here/'harness/files.json').read_text(),
    'autonomy/studies/architecture/harness/run-architecture-contract.py':'pass\n',
    'autonomy/studies/architecture/harness/run-architecture-weight-contract.py':'pass\n',
    'autonomy/studies/architecture/harness/run-architecture-learning-curve.py':'pass\n',
    'autonomy/studies/architecture/harness/audit-architecture-checkpoint.py':'pass\n',
    'autonomy/studies/architecture/harness/run-architecture-loss-audit.py':'pass\n',
    'autonomy/studies/architecture/harness/score-architecture-score-first.py':'pass\n',
    'autonomy/studies/architecture/harness/audit-architecture-score-first.py':'pass\n',
    'autonomy/studies/architecture/registry.json':(here/'registry.json').read_text(),
    'autonomy/pipeline/module.py':'pass\n',
    'autonomy/detection/worker.py':'pass\n',
    'autonomy/research/overfit-native-cache-progress.json':'{"admitted_frames":16,"selected_frames":16,"frame_evidence":{}}\n',
   })
   store=module.LocalSnapshotStore(root/'store')
   old=self.patch_module_paths(here,package_root,repo)
   try:
    source,package=module.make_snapshot(root/'run','residual_bev','trial-01',root/'cache',store=store,bazel=repo/'bazelw',runner=self.query_runner(pins))
   finally:
    self.restore_module_paths(old)
   self.assertEqual(package,source/'autonomy')
   self.assertTrue((package/'pipeline').is_dir())
   self.assertFalse((source/'experiments').exists())
 def test_new_run_metadata_pins_evidence_source_snapshot(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);repo=root/'repo';package_root,here=self.write_runner_fixture(repo)
   archive,digest,pins=self.archive({
    'autonomy/studies/architecture/harness/files.json':(here/'harness/files.json').read_text(),
    'autonomy/studies/architecture/harness/run-architecture-contract.py':'pass\n',
    'autonomy/studies/architecture/harness/run-architecture-weight-contract.py':'pass\n',
    'autonomy/studies/architecture/harness/run-architecture-learning-curve.py':'pass\n',
    'autonomy/studies/architecture/harness/audit-architecture-checkpoint.py':'pass\n',
    'autonomy/studies/architecture/harness/run-architecture-loss-audit.py':'pass\n',
    'autonomy/studies/architecture/harness/score-architecture-score-first.py':'pass\n',
    'autonomy/studies/architecture/harness/audit-architecture-score-first.py':'pass\n',
    'autonomy/studies/architecture/registry.json':(here/'registry.json').read_text(),
    'autonomy/pipeline/module.py':'pass\n',
    'autonomy/detection/worker.py':'pass\n',
    'autonomy/research/overfit-native-cache-progress.json':'{"admitted_frames":16,"selected_frames":16,"frame_evidence":{}}\n',
   })
   store=module.LocalSnapshotStore(root/'store');called=[]
   def runner(command,**kwargs):
    called.append(command)
    return self.query_runner(pins)(command,**kwargs)
   old=self.patch_module_paths(here,package_root,repo)
   try:
    source,package=module.make_snapshot(root/'run','residual_bev','trial-01',root/'cache',store=store,bazel=repo/'bazelw',runner=runner)
   finally:
    self.restore_module_paths(old)
   meta=json.loads((root/'run/run.json').read_text())
   self.assertEqual(meta['source_snapshot_sha256'],digest)
   self.assertEqual(meta['source_snapshot_target'],module.ARCHITECTURE_SOURCE_SNAPSHOT_TARGET)
   self.assertEqual(meta['source_snapshot_store'],{'schema_version':1,'kind':'local','root':str(root/'store')})
   self.assertEqual(meta['source_snapshot_archive_bytes'],len(archive))
   self.assertEqual(meta['source_pins'],pins)
   self.assertNotIn('source_sha256',meta)
   self.assertIn(module.ARCHITECTURE_SOURCE_SNAPSHOT_TARGET,called[0][-1])
   self.assertEqual(package,source/'autonomy')
   self.assertTrue((source/'.scratch/run-architecture-learning-curve.py').is_file())
   self.assertFalse((package/'research/unrelated-retained-evidence.json').exists())
 def test_check_snapshot_uses_recorded_snapshot_after_working_tree_changes(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);directory=root/'run';directory.mkdir();cache=root/'cache'
   archive,digest,pins=self.archive({'autonomy/detection/worker.py':'pinned\n'})
   atomic={'experiment':'residual_bev','run_id':'trial-01','label':'residual_bev--trial-01','cache_root':str(cache),'source_snapshot_sha256':digest,'source_snapshot_target':'//autonomy:architecture_experiment_runner_snapshot','source_pins':pins,'stages':[]}
   (directory/'run.json').write_text(json.dumps(atomic))
   original_receipt=(directory/'run.json').read_bytes()
   store=cache/'insula/source-snapshots-v1';store.mkdir(parents=True);(store/digest).write_bytes(archive)
   (root/'repo/autonomy/detection').mkdir(parents=True);(root/'repo/autonomy/detection/worker.py').write_text('changed after snapshot\n')
   self.assertEqual(module.check_snapshot(directory),atomic)
   materialized=directory/'source/autonomy/detection/worker.py'
   self.assertEqual(materialized.read_text(),'pinned\n')
   self.assertEqual((directory/'run.json').read_bytes(),original_receipt)
   self.assertEqual((store/digest).read_bytes(),archive)
   materialized.chmod(0o600)
   materialized.write_text('tampered materialization\n')
   with self.assertRaisesRegex(ValueError,'materialized source changed'):
    module.check_snapshot(directory)
   self.assertEqual(materialized.read_text(),'tampered materialization\n')
 def test_check_snapshot_rejects_corrupt_snapshot_object(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);directory=root/'run';cache=root/'cache';directory.mkdir()
   archive,digest,pins=self.archive({'autonomy/detection/worker.py':'pinned\n'})
   store=cache/'insula/source-snapshots-v1';store.mkdir(parents=True);(store/digest).write_bytes(b'corrupt')
   (directory/'run.json').write_text(json.dumps({'experiment':'residual_bev','run_id':'trial-01','label':'residual_bev--trial-01','cache_root':str(cache),'source_snapshot_sha256':digest,'source_snapshot_target':'//autonomy:architecture_experiment_runner_snapshot','source_pins':pins,'stages':[]}))
   with self.assertRaisesRegex(ValueError,'snapshot digest differs'):
    module.check_snapshot(directory)
 def test_stage_receipt_verification_checks_recorded_source_snapshot(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);store=root/'cache/insula/source-snapshots-v1';store.mkdir(parents=True)
   archive,digest,pins=self.archive({'autonomy/detection/worker.py':'pinned\n'});(store/digest).write_bytes(archive)
   receipt={'checks':[{'exit_code':0}],'artifacts':{},'source_snapshot_sha256':digest,'source_snapshot_target':'//autonomy:architecture_experiment_runner_snapshot','source_pins':pins}
   module.verify_receipt(receipt,root,snapshot_store=module.LocalSnapshotStore(store))
   (store/digest).write_bytes(b'corrupt')
   with self.assertRaisesRegex(ValueError,'snapshot digest differs'):
    module.verify_receipt(receipt,root,snapshot_store=module.LocalSnapshotStore(store))
 def test_cli_verify_uses_run_store_for_legacy_stage_receipts(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cache=root/'cache';directory=cache/'insula/architecture-runs/trial-01';package=directory/'source/autonomy';research=package/'research'
   directory.mkdir(parents=True)
   archive,digest,pins=self.archive({'autonomy/detection/worker.py':'pinned\n'})
   store=cache/'insula/source-snapshots-v1';store.mkdir(parents=True);(store/digest).write_bytes(archive)
   meta={'experiment':'residual_bev','run_id':'trial-01','label':'residual_bev--trial-01','cache_root':str(cache),'source_snapshot_sha256':digest,'source_snapshot_target':module.ARCHITECTURE_SOURCE_SNAPSHOT_TARGET,'source_pins':pins,'stages':module.stages_for('residual_bev')}
   (directory/'run.json').write_text(json.dumps(meta))
   materialize_receipt_sources(meta,directory/'source',module.LocalSnapshotStore(store))
   research.mkdir()
   for stage in module.stages_for('residual_bev'):
    path=module.receipt_path(package,stage,'residual_bev--trial-01')
    path.write_text(json.dumps({'checks':[{'exit_code':0}],'artifacts':{},'source_snapshot_sha256':digest,'source_snapshot_target':module.ARCHITECTURE_SOURCE_SNAPSHOT_TARGET,'source_pins':pins}))
   def fake_summary(package_arg,name,label,snapshot_store=None):
    self.assertIsNotNone(snapshot_store)
    for stage in module.stages_for(name):
     module.verify_receipt(json.loads(module.receipt_path(package_arg,stage,label).read_text()),package_arg,snapshot_store=snapshot_store)
    return {'verified':True}
   old=module.summarize
   module.summarize=fake_summary
   try:
    self.assertEqual(module.main(['--cache-root',str(cache),'verify','residual_bev','--run-id','trial-01']),0)
   finally:
    module.summarize=old
 def test_existing_stage_receipt_is_pinned_before_resume_skip_verifies_it(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cache=root/'cache';run=cache/'insula/architecture-runs/trial-01';package=run/'source/autonomy';research=package/'research';logs=run/'logs'
   logs.mkdir(parents=True)
   archive,digest,pins=self.archive({'autonomy/detection/worker.py':'pinned\n'})
   store=cache/'insula/source-snapshots-v1';store.mkdir(parents=True);(store/digest).write_bytes(archive)
   meta={'experiment':'residual_bev','run_id':'trial-01','label':'residual_bev--trial-01','cache_root':str(cache),'source_snapshot_sha256':digest,'source_snapshot_target':module.ARCHITECTURE_SOURCE_SNAPSHOT_TARGET,'source_pins':pins,'stages':module.stages_for('residual_bev')}
   (run/'run.json').write_text(json.dumps(meta))
   materialize_receipt_sources(meta,run/'source',module.LocalSnapshotStore(store))
   research.mkdir()
   for stage in module.stages_for('residual_bev'):
    if stage['name']=='contract':(research/'architecture-contract-verified.json').write_text(json.dumps({'checks':[{'exit_code':0}],'artifacts':{}}))
    else:(logs/(stage['name']+'.log')).write_text('stop before later stages\n')
   with self.assertRaisesRegex(ValueError,'Incomplete stage weights'):
    module.execute('residual_bev','trial-01',cache,resume=True)
   receipt=json.loads((research/'architecture-contract-verified.json').read_text())
   self.assertEqual(receipt['source_snapshot_sha256'],digest)
   self.assertEqual(receipt['source_pins'],pins)
 def test_verify_without_run_id_is_retired(self):
  with self.assertRaises(SystemExit):
   module.main(['verify','residual_bev'])
if __name__=='__main__':unittest.main()
