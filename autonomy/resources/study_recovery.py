"""Preserve admitted history and cache-local evidence across interruptions."""
import json,shutil
from pathlib import Path
from resources.scientific_payload import sha

def restore_curve(previous):
 curve=json.loads(json.dumps(previous.get('curve',[])))
 steps=[point['step'] for point in curve]
 if any(type(step) is not int or step<0 for step in steps) or len(set(steps))!=len(steps):raise ValueError('unique nonnegative checkpoint steps required')
 return sorted(curve,key=lambda point:point['step'])

def retain_admission(receipt,run):
 receipt,run=Path(receipt),Path(run);digest=sha(receipt);destination=run/'architecture-admission.json'
 if destination.exists():
  if sha(destination)!=digest:raise ValueError('immutable admission differs')
 else:
  with receipt.open('rb') as source,destination.open('xb') as output:shutil.copyfileobj(source,output)
 if sha(destination)!=digest:raise ValueError('admission copy differs')
 return {'path':str(destination),'sha256':digest}

def recover_checkpoint(output):
 import os
 output=Path(output);current=output/'checkpoint.pt';prior=output/'resume/checkpoint.pt'
 if current.exists() or not prior.exists():return False
 report=json.loads((output/'check.json').read_text())
 if sha(prior)!=report['checkpoint_sha256']:raise ValueError('interrupted checkpoint does not match admitted producer report')
 os.replace(prior,current)
 return True
