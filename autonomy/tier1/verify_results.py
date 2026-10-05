"""Read-only release-aware closure of native curves, source pins and replay receipts."""
import hashlib,json,sys
from pathlib import Path
from tier1.admission import fit_interval
from tier1.receipt_lifecycle import admit_artifact
from tier1.storage import unique_payload_bytes

HOST_CACHE=None
def resolved(p):
 p=Path(p)
 return Path('/source')/p.relative_to(HOST_CACHE) if HOST_CACHE is not None and (p==HOST_CACHE or HOST_CACHE in p.parents) else p
def read(p):return resolved(p).read_text()
def sha(p):
 with resolved(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify(result_path):
 global HOST_CACHE
 result=json.loads(Path(result_path).read_text());run=Path(result['run_directory'])
 if Path('/tmp/offline-verifier').exists():HOST_CACHE=run.parents[1]
 meta=json.loads(read(run/'run.json'));assert sha(run/'run.json')==result['metadata_sha256'];source=run/'source'
 for p,h in meta['source_sha256'].items():assert sha(source/p)==h
 if result.get('finished',False):
  assert set(result['cases'])==set(meta['matrix'])
  assert all(c['status'] in ['sustained native overfit','failed to overfit by 10000 updates','exact observation equivalence control'] for c in result['cases'].values())
 output=[];checked=0
 for name,case in result['cases'].items():
  if name=='all_pillars':
   if result.get('finished',False):
    receiptpath=case['terminal_GPU_equivalence_receipt'];assert sha(receiptpath)==case['terminal_GPU_equivalence_receipt_sha256'];control=json.loads(read(receiptpath));assert control['exit_code']==0
    for p,h in control['source_and_input_sha256'].items():assert sha(p)==h
    for p,h in control['artifacts'].items():assert sha(p)==h
    assert control['validation']['initial_full_heads_exact_on_GPU'] and control['validation']['terminal_full_heads_exact_to_baseline_producer']
    assert control['validation']['inherited_native_LEVEL2_per_class']==result['cases']['baseline']['curve'][-1]['LEVEL2_per_class']
   continue
  if case['status'] not in ['sustained native overfit','failed to overfit by 10000 updates']:
   output.append({'case':name,'status':case['status'],'time_to_fit':fit_interval(case.get('curve',[]))});continue
  released=json.loads(read(run/name/'snapshot-release.json'));assert sha(run/name/'snapshot-release.json')==case['snapshot_release_sha256'];release_lookup={entry['path']:entry['sha256'] for entry in released['released']};superseded=set()
  ledger=run/name/'model-supersessions.json'
  if resolved(ledger).exists():superseded={entry['old_sha256'] for entry in json.loads(read(ledger))}
  replay=False;proposal_steps=set();metric_steps=set();losses=False;loss_counts={};native_scores={}
  for reference in case['verification_receipts']:
   assert sha(reference['receipt'])==reference['sha256'];receipt=json.loads(read(reference['receipt']));assert receipt['metadata_sha256']==result['metadata_sha256'] and receipt['exit_code']==0
   for p,h in receipt['artifacts'].items():assert sha(p)==h
   for p,h in receipt.get('override_source_sha256',{}).items():assert sha(p)==h
   for p,h in receipt.get('transient_artifacts',{}).items():
    admit_artifact(p,h,release_lookup,superseded,resolved(p))
   validation=receipt['validation'] or {};stage=receipt['name']
   if '-replay-' in stage and int(stage.rsplit('-',1)[1])==case['updates']:assert validation['exact_terminal_model_and_adam'] and validation['exact_all_checkpoint_heads'] and validation['exact_rng'];replay=True
   if '-proposal-audit-' in stage:assert validation['literal_score_first_decode_nms_and_measurement_metadata'] and validation['all_native_eligible_GT_retained'] and validation['eligible_groundtruth']==73;proposal_steps.add(int(stage.rsplit('-',1)[1]))
   if '-metric-audit-' in stage:assert validation['native_metric_replay_exact'] and validation['all_export_fields_independently_reread'];metric_steps.add(int(stage.rsplit('-',1)[1]))
   if '-score-' in stage:native_scores[int(stage.rsplit('-',1)[1])]=validation['LEVEL2_per_class']
   if '-loss-' in stage:
    count=validation['literal_checkpoint_losses'];assert count>0;losses=True;target=int(stage.rsplit('-',1)[1]);assert target not in loss_counts or loss_counts[target]==count;loss_counts[target]=count
   checked+=1
  steps={point['step'] for point in case['curve']};assert proposal_steps==metric_steps==steps and replay and losses
  previous=None;loss_covered=set()
  for target,count in sorted(loss_counts.items()):
   new={step for step in steps if step<=target and (previous is None or step>previous)}
   expected=len(new)+(2 if previous is not None and previous>0 else 0)
   assert count==expected,(name,target,count,expected);loss_covered.update(new);previous=target
  assert loss_covered==steps
  for point in case['curve']:
   values=point['LEVEL2_per_class'];assert values==native_scores[point['step']];assert set(values)=={'1','2','3','4'};assert point['all_class_quality_passed']==all(v['APH']>=.8 for v in values.values())
  expected=len(case['curve'])>=2 and all(p['all_class_quality_passed'] for p in case['curve'][-2:]);assert (case['status']=='sustained native overfit')==expected
  directory=Path(case['output_directory']);training=json.loads(read(directory/'check.json'));assert sha(directory/'checkpoint.pt')==training['checkpoint_sha256'] and training['case']==meta['matrix'][name]
  assert training['updates']==case['updates']==case['curve'][-1]['step']
  original_curve={point['step']:point for point in training['checkpoint_curve']};assert set(original_curve)==steps
  for point in case['curve']:
   for key,value in original_curve[point['step']].items():assert point[key]==value,(name,point['step'],key)
  assert case['parameters']==training['parameters'] and case['cumulative_train_seconds']==training['cumulative_train_seconds'] and case['clipped_steps']==training['clipped_steps']
  fit=fit_interval(case['curve']);train_stages=[json.loads(read(r['receipt'])) for r in case['verification_receipts']];native_seconds=sum(x['elapsed_seconds'] for x in train_stages if '-score-' in x['name'] or '-metric-audit-' in x['name']);output.append({'case':name,'status':case['status'],'parameters':case['parameters'],'updates':case['updates'],'time_to_fit':fit,'cumulative_train_seconds':case['cumulative_train_seconds'],'native_compute_seconds_sum':native_seconds,'terminal_LEVEL2_per_class':case['curve'][-1]['LEVEL2_per_class'],'clipped_steps':case['clipped_steps']})
 used=unique_payload_bytes(resolved(run.parents[1]/'scientific-processing'));assert used<=15*1024**3
 return {'rows':output,'verified_stage_receipts':checked,'unique_scientific_payload_bytes':used,'all_cases_finished':result.get('finished',False),'scope':'training-only fixed-one-frame fitting; two consecutive native four-class APH >= .8; no heldout claim'}
if __name__=='__main__':
 p=Path(sys.argv[1]);r=verify(p);out=p.with_name(p.stem+'-closed.json');out.write_text(json.dumps(r,indent=2));print('ADMITTED release-aware results',len(r['rows']),r['verified_stage_receipts'])
