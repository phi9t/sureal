"""Keep-two orchestration over independently admitted native checkpoints.

The backend is responsible for source/receipt admission, live stage execution,
full HDFS recovery/union before release, and durable state. This module never
turns loss or an unverified producer report into model-quality evidence.
"""
import copy
from cohort.sustained_control import decide_next

def execute_case(backend,records=None):
 records=copy.deepcopy(records or []);backend.validate_resume(records)
 def retire(record):
  publication=backend.publish_and_release(record)
  record['publication']=publication;record['released']=True
  backend.persist(records)
 while True:
  if records:
   decision=decide_next([r['sample'] for r in records],records[-1]['report'])
   if decision['action']=='stop':
    backend.persist(records,decision)
    for record in records:
     if not record['released']:retire(record)
    backend.persist(records,decision)
    return records,decision
   target=decision['target_step']
  else:target=0
  previous=records[-1] if records else None
  record=backend.train_and_admit(previous,target)
  if record['released'] or record['sample']['step']!=record['step'] or record['report']['updates']!=record['step']:raise ValueError('new exact unreleased checkpoint required')
  if previous is not None and record['step']==previous['step']:
   if record['report']['stop_reason']!='time_cap' or record['sample']!=previous['sample']:raise ValueError('no-progress terminal requires independently identical native sample')
   decision=decide_next([r['sample'] for r in records],record['report'])
   if decision['action']!='stop':raise ValueError('no-progress continuation forbidden')
   backend.persist(records,decision,diagnostic=record)
   for old in records:
    if not old['released']:retire(old)
   record['publication']=backend.publish_and_release(record);record['released']=True
   backend.persist(records,decision,diagnostic=record)
   return records,decision
  decide_next([r['sample'] for r in records]+[record['sample']],record['report'])
  records.append(record);backend.persist(records)
  # Keep the latest two; only a fully admitted newer sample retires older bytes.
  for old in records[:-2]:
   if not old['released']:retire(old)
