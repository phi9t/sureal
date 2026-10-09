"""Frozen training-only continuation gate; no model-quality promotion by loss."""
import copy,re
from evidence.score_records import read_level2_per_class

GRID=(0,1000,2000,4000,8000,12000,16000,24000,32000)
RECIPES=('baseline','residual_bev','class_balanced','prior_bias')

def validate_contract(candidate,admitted_frames):
 expected={'schema_version':1,'seed':17,'recipes':list(RECIPES),'max_updates':32000,'max_training_seconds':7200,'checkpoint_grid':list(GRID),'confirmation_gap':1000,'decoder_version':3,'APH_threshold':.8}
 if not isinstance(candidate,dict) or set(candidate)!=set(expected)|{'frames'}:raise ValueError('complete exact contract required')
 for key,value in expected.items():
  if candidate[key]!=value or type(candidate[key]) is not type(value):raise ValueError('changed execution contract: '+key)
 frames=candidate['frames']
 if not isinstance(frames,list) or len(frames)!=16 or frames!=admitted_frames:raise ValueError('exact sixteen admitted frames required')
 seen=set()
 for frame in frames:
  if not isinstance(frame,dict) or set(frame)!= {'identity','split','sha256'} or frame['split']!='training' or not isinstance(frame['identity'],str) or not frame['identity'] or frame['identity'] in seen:raise ValueError('unique training identities required')
  seen.add(frame['identity']);hashes=frame['sha256']
  if not isinstance(hashes,dict) or set(hashes)!={'observations.npz','targets.npz','report.json'} or any(not isinstance(h,str) or re.fullmatch('[0-9a-f]{64}',h) is None for h in hashes.values()):raise ValueError('complete admitted observation/target/report hashes required')
 return copy.deepcopy(candidate)

def next_checkpoint(step,first_pass_step):
 if type(step) is not int or not 0<=step<=32000:raise ValueError('bounded update required')
 candidates=[x for x in GRID if x>step]
 if first_pass_step is not None:
  if type(first_pass_step) is not int or not 0<=first_pass_step<=step:raise ValueError('observed first pass required')
  confirmation=first_pass_step+1000
  if step<confirmation<=32000:candidates.append(confirmation)
 return min(candidates) if candidates else None

def sample_aph(sample):
 if 'LEVEL2_per_class' in sample:return {key:row['APH'] for key,row in read_level2_per_class(sample['LEVEL2_per_class']).items()}
 if 'APH' in sample:return {key:row['APH'] for key,row in read_level2_per_class({key:{'AP':value,'APH':value} for key,value in sample['APH'].items()}).items()}
 raise ValueError('native score record required')

def fit_status(samples,terminal_step,stop_reason):
 if type(terminal_step) is not int or not 0<=terminal_step<=32000 or stop_reason not in {'gate','update_cap','time_cap'}:raise ValueError('bounded stop reason required')
 if stop_reason=='update_cap' and terminal_step!=32000:raise ValueError('update cap not reached')
 if not samples or samples[-1]['step']!=terminal_step:raise ValueError('terminal scored checkpoint required')
 passing=[];previous=-1;first_pass=None
 for sample in samples:
  step=sample['step'];aph=sample_aph(sample)
  if type(step) is not int or not previous<step<=terminal_step:raise ValueError('ordered class-complete checkpoints required')
  expected=0 if previous==-1 else next_checkpoint(previous,first_pass)
  forced_time_terminal=previous>=0 and stop_reason=='time_cap' and step==terminal_step and expected is not None and previous<step<expected
  if step!=expected and not forced_time_terminal:raise ValueError('missing or premature checkpoint')
  if len(passing)>=2 and all(passing[-2:]):raise ValueError('continued after sustained stop')
  passed=all(x>=.8 for x in aph.values());passing.append(passed)
  if passed and first_pass is None:first_pass=step
  previous=step
 if len(passing)>=2 and all(passing[-2:]) and not forced_time_terminal:return 'sustained native overfit'
 if stop_reason=='gate':raise ValueError('native sustained gate did not pass')
 if passing[-1]:return 'unconfirmed terminal pass'
 if stop_reason=='time_cap':return 'training-time censored without sustained overfit'
 return 'failed to overfit by 32000 updates'
