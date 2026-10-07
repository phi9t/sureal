"""Pre-write scientific budget admission and sampled sustained-fit timing."""
from resources.scientific_payload import unique_payload_bytes

def reserve_write(root,maximum_new_bytes,limit=15*1024**3):
 used=unique_payload_bytes(root)
 if used+maximum_new_bytes>limit:raise ValueError(f'Scientific write refused before allocation: {used}+{maximum_new_bytes}>{limit}')
 return {'used_bytes_before':used,'maximum_new_bytes':maximum_new_bytes,'limit':limit}

def fit_interval(curve):
 if not curve:return {'right_censored':True,'observed_updates':0,'reason':'no admitted checkpoints'}
 # First sampled pair certifies fit, even if later regression is explicitly retained.
 for i in range(1,len(curve)):
  if curve[i-1]['all_class_quality_passed'] and curve[i]['all_class_quality_passed']:
   lo=curve[i-2] if i>=2 else {'step':0,'cumulative_train_seconds':0}
   return {'right_censored':False,'first_stable_fit_update_interval':[lo['step'],curve[i-1]['step']],'first_stable_fit_train_seconds_interval':[lo['cumulative_train_seconds'],curve[i-1]['cumulative_train_seconds']],'confirmation_update':curve[i]['step'],'confirmation_train_seconds':curve[i]['cumulative_train_seconds'],'terminal_pair_passed':len(curve)>=2 and all(x['all_class_quality_passed'] for x in curve[-2:])}
 return {'right_censored':True,'observed_updates':curve[-1]['step'],'observed_train_seconds':curve[-1]['cumulative_train_seconds'],'terminal_pair_passed':False}
