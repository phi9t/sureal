"""Pure preregistered scheduling; callers must independently admit every sample.

This module never validates stage receipts, publishes checkpoints or promotes
scientific training. The controller must complete those separate gates first.
"""
import math
from cohort.sustained_contract import next_checkpoint,fit_status

def decide_next(samples,report):
 if not isinstance(samples,list) or not samples:raise ValueError('scored initial checkpoint required')
 required={'updates','requested_updates','stop_reason','cumulative_train_seconds','resource_gate_passed'}
 if not isinstance(report,dict) or not required<=set(report):raise ValueError('complete producer stop/resource fields required')
 terminal=report['updates'];requested=report['requested_updates'];reason=report['stop_reason'];seconds=report['cumulative_train_seconds'];admitted=report['resource_gate_passed']
 if type(terminal) is not int or type(requested) is not int or not 0<=terminal<=requested<=32000 or reason not in {'sample','time_cap','resource_overrun'} or type(admitted) is not bool:raise ValueError('bounded original producer outcome required')
 if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<0:raise ValueError('finite synchronized training seconds required')
 if reason=='resource_overrun':
  if admitted:raise ValueError('resource failure cannot be admitted')
 elif not admitted or seconds>7200:raise ValueError('resource admission contradicts producer budget')
 # fit_status validates all four finite classes and the complete sample order,
 # including an honestly stopped terminal interval before its requested grid.
 status=fit_status(samples,terminal,'time_cap')
 history=samples[:-1];first_pass=next((s['step'] for s in history if all(v>=.8 for v in s['APH'].values())),None)
 expected=0 if not history else next_checkpoint(history[-1]['step'],first_pass)
 if requested!=expected:
  all_first=next((s['step'] for s in samples if all(v>=.8 for v in s['APH'].values())),None)
  no_progress_stop=reason in {'time_cap','resource_overrun'} and requested==next_checkpoint(terminal,all_first)
  if not no_progress_stop:raise ValueError('requested chunk differs from frozen checkpoint schedule')
 if reason=='sample' and terminal!=requested:raise ValueError('sample did not reach requested update')
 if reason=='resource_overrun':return {'action':'stop','status':'resource censored; promotion forbidden','resource_admitted':False,'terminal_step':terminal}
 if reason=='time_cap' and terminal<requested:
  bounded_status='unconfirmed terminal pass' if all(v>=.8 for v in samples[-1]['APH'].values()) else 'training-time censored without sustained overfit'
  return {'action':'stop','status':bounded_status,'resource_admitted':True,'terminal_step':terminal}
 if status=='sustained native overfit':return {'action':'stop','status':fit_status(samples,terminal,'gate'),'resource_admitted':True,'terminal_step':terminal}
 if reason=='time_cap':return {'action':'stop','status':status,'resource_admitted':True,'terminal_step':terminal}
 if terminal==32000:return {'action':'stop','status':fit_status(samples,terminal,'update_cap'),'resource_admitted':True,'terminal_step':terminal}
 first_pass=next((s['step'] for s in samples if all(v>=.8 for v in s['APH'].values())),None)
 return {'action':'train','target_step':next_checkpoint(terminal,first_pass),'resource_admitted':True,'status':'awaiting next independently admitted native sample'}
