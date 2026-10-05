"""Wait for strict run admissions, score residual, summarize matched candidates."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;C=Path.home()/'.cache/waystone/waymo-perception';report=P.parent/'research/balanced-study-recovery-20261002.json'
ids={'baseline':'balanced20261002a','residual_bev':'balanced20261002b'};state={'stage':'waiting_for_residual_replays','run_ids':ids,'scope':'training-only balanced16; native gates before larger training'}
def save():report.write_text(json.dumps(state,indent=2)+'\n')
save();deadline=time.monotonic()+1800
while not (C/'insula/cohort16-residual_bev-balanced20261002b/loss-verified.json').is_file():
 if time.monotonic()>deadline:raise TimeoutError('Residual replay admission missing')
 time.sleep(10)
state['stage']='native_scoring';save();r=subprocess.run([sys.executable,str(P/'score_balanced.py'),'residual_bev','--run-id',ids['residual_bev']]);assert r.returncode==0
results={}
for variant,runid in ids.items():
 quality=P.parent/'research'/f'cohort16-{variant}-{runid}-quality-v2.json'
 while not quality.is_file() or len(json.loads(quality.read_text())['curve'])!=3:
  if time.monotonic()>deadline+7200:raise TimeoutError('Baseline native scoring incomplete')
  time.sleep(10)
 q=json.loads(quality.read_text());run=C/'insula'/f'cohort16-{variant}-{runid}';sys.path.insert(0,str(P));from admissions import required_fit_admissions
 admissions=required_fit_admissions(run);train=json.loads((run/'train-verified.json').read_text())['validation']
 for p,h in q['artifacts'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
 results[variant]={'run_id':runid,'native_curve':q['curve'],'full_class_fit_passed':q['full_class_fit_passed'],'initial_mean_loss':train['initial_mean_loss'],'final_mean_loss':train['final_mean_loss'],'cumulative_train_seconds':train['cumulative_train_seconds'],'parameters':train['parameters'],'quality_receipt':str(quality),'quality_sha256':hashlib.sha256(quality.read_bytes()).hexdigest(),'required_admissions':admissions}
# Match the immutable inputs, identity order, seed, and recipe across candidates.
a,b=[json.loads((C/'insula'/f'cohort16-{v}-{ids[v]}'/'run.json').read_text())['manifest'] for v in ids];assert a['frames']==b['frames'] and a['execution']==b['execution']
state.update(stage='completed',results=results,matched_inputs_and_recipe=True,full_dataset_readiness=any(r['full_class_fit_passed'] for r in results.values()));save();print('COMPLETE matched fitting study; native gate',state['full_dataset_readiness'],flush=True)
