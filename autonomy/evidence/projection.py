"""Project immutable/native evidence into explicit experiment lifecycle stages."""
import copy
from evidence.score_records import LEVEL2_CLASS_KEYS, populated_level2_classes, read_level2_per_class
GOAL='Fit the fixed 73-object all-class frame; measure updates and synchronized training time under the declared recipe.'
ACCEPTANCE='All four native LEVEL2 APH >= 0.80 at two consecutive sampled checkpoints including terminal; exact full replay and final live closure. Otherwise unchanged 10000-update censored result.'
VERIFIERS=['live actual-frame architecture gradient/resource admission','independent literal losses','native proposal/GT/export/metric audits','exact model/Adam/RNG/head replay','final live Insula closure']
def score_record_classes(point):
 for source in [point,point.get('preparation') if isinstance(point,dict) else None]:
  if isinstance(source,dict) and 'groundtruth_by_class' in source:
   return populated_level2_classes(source)
 if isinstance(point,dict) and point.get('all_class_quality_passed') is not None:
  return LEVEL2_CLASS_KEYS
 record=point.get('LEVEL2_per_class') if isinstance(point,dict) else None
 if isinstance(record,dict):
  keys=tuple(key for key in LEVEL2_CLASS_KEYS if key in record)
  if keys and set(record)==set(keys):
   return keys
 return LEVEL2_CLASS_KEYS
def score_record(point):
 if 'LEVEL2_per_class' not in point:return None
 return read_level2_per_class(point['LEVEL2_per_class'],classes=score_record_classes(point))
def quality(point):
 values=score_record(point)
 return values is not None and all(v['APH']>=.8 for v in values.values())
def project_experiments(run_id,recipes,result,result_sha256,closure,admission):
 result=result or {'cases':{}}
 if set(result['cases'])-set(recipes):raise ValueError('result contains unknown experiment recipes')
 closed=False
 if closure:
  if closure['candidate_sha256']!=result_sha256 or not closure['validation']['all_cases_finished'] or any(check['exit_code']!=0 for check in closure['checks']):raise ValueError('final closure does not match result')
  closed=True
 rows=[]
 for name,recipe in recipes.items():
  case=result['cases'].get(name,{});curve=case.get('curve',[]);status=case.get('status');stage='planned';control=status=='exact observation equivalence control'
  parsed_scores=[score_record(point) for point in curve]
  proof=(admission or {}).get('cases',{}).get(name,{}).get('validation',{})
  if status:
   expected=(result.get('_run_metadata') or {}).get('matrix',{}).get(name)
   if expected is None or recipe!=expected:raise ValueError('registry recipe differs from immutable run recipe')
  if proof.get('exact_repeated_three_update_model_adam_rng'):
   if recipe!=proof.get('case'):raise ValueError('registry recipe differs from GPU admission recipe')
   stage='gpu_admitted'
  if status=='sustained native overfit':
   if len(curve)<2 or not all(quality(point) for point in curve[-2:]):raise ValueError('claimed overfit fails native threshold')
   stage='verified_overfit' if closed else 'native_fit_pending_closure'
  elif status=='failed to overfit by 10000 updates':
   if case['updates']!=10000:raise ValueError('censored result requires full budget')
   stage='verified_censored' if closed else 'censored_pending_closure'
  elif control:stage='verified_equivalence_control' if closed else 'equivalence_pending_closure'
  elif status=='execution failed; artifacts retained':stage='execution_failed'
  elif status:stage='running_or_verifying'
  values=parsed_scores[-1] if parsed_scores else None;values=values or {};minimum=min((v['APH'] for v in values.values()),default=None)
  rows.append({'id':run_id+'/'+name,'run_id':run_id,'name':name,'goal':GOAL,'recipe':copy.deepcopy(recipe),'verifiers':VERIFIERS.copy(),'acceptance':ACCEPTANCE,'stage':stage,'trained':not control and bool(curve) and max(p['step'] for p in curve)>0,'updates':case.get('updates'),'confirmation_update':(case.get('time_to_fit') or {}).get('confirmation_update'),'time_to_fit':case.get('time_to_fit'),'cumulative_train_seconds':case.get('cumulative_train_seconds'),'terminal_LEVEL2_per_class':values,'worst_terminal_APH':minimum,'result_sha256':result_sha256,'closure_candidate_sha256':closure.get('candidate_sha256') if closure else None})
 return rows
