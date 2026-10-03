"""Sequential bounded GPU runs followed by native all-class scoring."""
import argparse,json,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);a=parser.parse_args();assert a.run_id.isalnum()
report=P.parent/'research'/f'balanced-study-{a.run_id}.json'
state={'run_id':a.run_id,'variants':['baseline','residual_bev'],'stage':'waiting_for_native_admission','checkpoint_grid':[0,1000,2000],'updates_per_candidate':2000,'scope':'balanced16 training-only fit; full-dataset training remains quality gated','completed':[]}
def save():report.write_text(json.dumps(state,indent=2)+'\n')
save();deadline=time.monotonic()+1800
while True:
 progress=P.parent/'research/balanced16-native-progress.json'
 if progress.is_file() and json.loads(progress.read_text())['admitted_frames']==16:break
 if time.monotonic()>deadline:raise TimeoutError('Native cache admission not complete; no GPU run launched')
 time.sleep(10)
for worker,stage in [('run_balanced.py','training'),('score_balanced.py','native_scoring')]:
 for variant in state['variants']:
  state['stage']=stage;state['active_variant']=variant;save();command=[sys.executable,str(P/worker),variant,'--run-id',a.run_id];print('LAUNCH',stage,variant,flush=True);result=subprocess.run(command)
  if result.returncode:state['stage']='failed';state['failed_command']=command;save();sys.exit(result.returncode)
  state['completed'].append({'stage':stage,'variant':variant,'exit_code':0});save()
state['stage']='completed';state.pop('active_variant',None);save()
