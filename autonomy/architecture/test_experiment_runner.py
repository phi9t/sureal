import ast,importlib.util,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
p=Path(__file__).with_name('experiment_runner.py');spec=importlib.util.spec_from_file_location('experiment_runner',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class RunnerTests(unittest.TestCase):
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
 def test_worker_binding_is_not_confused_with_python_invocation(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'worker.py';p.write_text('worker')
   receipt={'artifacts':{},'worker_sha256':module.sha(p),'checks':[{'exit_code':0,'command':['--ro-bind',str(p),'/tmp/worker.py','--','python','/tmp/worker.py']}]}
   module.verify_receipt(receipt,Path(tmp))
 def test_namespacing_changes_receipts_but_not_model_variant(self):
  source="variant=sys.argv[1];assert variant in ['residual_bev']\nevidence=code/('research/architecture-'+variant+'-execution-verified.json')\nmanifest={'architecture_variant':variant}\n"
  patched=module.parameterize_driver(source)
  self.assertIn("'architecture_variant':variant",patched)
  self.assertIn("'run_label':run_label",patched)
  self.assertIn("'research/architecture-'+run_label",patched)
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
   root=Path(tmp);repo=root/'repo';package_root=repo/'autonomy';here=package_root/'architecture'
   for path in [package_root/'pipeline',package_root/'gpu',package_root/'research',here/'harness',repo/'docs/superpowers/specs']:
    path.mkdir(parents=True)
   (package_root/'pipeline/module.py').write_text('pass\n')
   (package_root/'gpu/worker.py').write_text('pass\n')
   (package_root/'research/evidence.json').write_text('{}\n')
   (repo/'docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md').write_text('# spec\n')
   (here/'registry.json').write_text(json.dumps({'residual_bev':{'status':'runnable','title':'Residual BEV'}}))
   drivers=[stage['driver'] for stage in module.stages_for('residual_bev')]
   (here/'harness/files.json').write_text(json.dumps(drivers))
   for driver in drivers:
    (here/'harness'/driver).write_text('pass\n')
   old_here,old_package,old_repo=module.HERE,module.PACKAGE,module.REPO
   module.HERE,module.PACKAGE,module.REPO=here,package_root,repo
   try:
    source,package=module.make_snapshot(root/'run','residual_bev','trial-01',root/'cache')
   finally:
    module.HERE,module.PACKAGE,module.REPO=old_here,old_package,old_repo
   self.assertEqual(package,source/'autonomy')
   self.assertTrue((package/'pipeline').is_dir())
   self.assertFalse((source/'experiments').exists())
if __name__=='__main__':unittest.main()
