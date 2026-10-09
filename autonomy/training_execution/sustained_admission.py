"""Reconcile semantic bindings after all separately pinned live native stages.

This does not replace stage execution, source/input/output hashes or independent
math. The controller must admit those receipts before calling this function.
"""
from evidence.score_records import LEVEL2_CLASS_KEYS, read_level2_per_class

def admit_sample(*,manifest,manifest_sha256,producer,producer_sha256,replay,transition,previous_checkpoint_sha256,start_step,loss,proposals,score,metric):
 try:
  step=producer['updates'];identities=[f['identity'] for f in manifest['frames']];heads=producer['head_hashes'];checkpoint=producer['checkpoint_sha256']
  if type(step) is not int or type(start_step) is not int or not 0<=start_step<=step<=32000 or step-start_step>8000 or len(identities)!=16 or len(set(identities))!=16 or set(heads)!={f'heads-{i:02d}.npz' for i in range(16)}:raise ValueError('complete bounded native checkpoint required')
  for report in [producer,replay,transition]:
   if report['manifest_sha256']!=manifest_sha256 or report['checkpoint_sha256']!=checkpoint:raise ValueError('checkpoint/manifest differs across stages')
  if producer['resource_gate_passed'] is not True:raise ValueError('producer resources not admitted')
  for report in [producer,transition]:
   for key,cap in [('peak_allocated_bytes',8*1024**3),('peak_rss_kib',16*1024**2)]:
    if type(report[key]) is not int or not 0<=report[key]<=cap:raise ValueError('native stage resource cap differs')
  if replay['updates']!=step or replay['head_hashes']!=heads or replay['checked_frames']!=identities:raise ValueError('exact ordered full16 head replay required')
  if transition['previous_checkpoint_sha256']!=previous_checkpoint_sha256 or transition['start_step']!=start_step or transition['terminal_step']!=step or transition['literal_updates']!=step-start_step or transition['state_exact_excluding_training_seconds'] is not True or transition['producer_synchronized_seconds_reconciled'] is not True:raise ValueError('complete independent native transition required')
  if loss['manifest_sha256']!=manifest_sha256 or loss['report_sha256']!=producer_sha256 or loss['frames']!=16 or loss['recipe']!=manifest['recipe'] or loss['updates']!=step or loss['head_hashes']!=heads or [r['identity'] for r in loss['rows']]!=identities:raise ValueError('literal full16 losses differ')
  if proposals['frames']!=16 or proposals['literal_score_first_decode_nms_and_measurement_metadata'] is not True or proposals['all_native_GT_retained'] is not True:raise ValueError('literal full native proposals/GT required')
  if score['decoder_version']!=3 or score['groundtruth_policy']!='all native four-class boxes; native evaluator handles eligibility' or score['manifest_sha256']!=manifest_sha256 or score['head_hashes']!=heads or [r['identity'] for r in score['frames']]!=identities or score['native_groundtruth']!=proposals['native_groundtruth'] or score['predictions']!=proposals['predictions']:raise ValueError('score/export/proposal identity differs')
  if metric['all_export_fields_independently_reread'] is not True or metric['native_metric_replay_exact'] is not True:raise ValueError('independent native protobuf/metric replay required')
  classes=read_level2_per_class(score['LEVEL2_per_class'],classes=LEVEL2_CLASS_KEYS)
  passed=all(row['APH']>=.8 for row in classes.values())
  if any(report[key] is not passed for report,key in [(score,'all_class_APH_gate_passed'),(score,'APH_gate_passed'),(metric,'all_class_APH_gate_passed')]):raise ValueError('native checkpoint gate differs across stages')
  return {'step':step,'APH':{k:row['APH'] for k,row in classes.items()}}
 except (KeyError,TypeError,AttributeError) as error:raise ValueError('complete native stage reports required') from error
