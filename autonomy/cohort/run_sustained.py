"""Execute the approved fixed16 one-factor comparison, with live gates throughout."""
import argparse,json,re,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
from resources.scientific_payload import sha
from cohort.sustained_controller_lock import acquire_experiment_lock
from cohort.sustained_controller_backend import NativeBackend,write,C
from cohort.sustained_workflow import execute_case
from cohort.sustained_contract import RECIPES

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);parser.add_argument('--resume',action='store_true');parser.add_argument('--admission-only',action='store_true');args=parser.parse_args()
 if re.fullmatch('[A-Za-z0-9]{1,64}',args.run_id) is None:raise ValueError('bounded alphanumeric run ID required')
 results=P/'research/advanced-expanded20261002a-results.json';closure=P/'research/advanced-closure-expanded20261002a-verified.json';evidence=json.loads(closure.read_text());matrix=json.loads(results.read_text())
 if evidence['candidate_sha256']!=sha(results) or evidence['validation']['all_cases_finished'] is not True or len(evidence['validation']['rows'])!=8 or matrix['finished'] is not True or any(sha(path)!=digest for path,digest in evidence['artifacts'].items()):raise ValueError('independent full expanded closure required')
 with acquire_experiment_lock(C/'insula/architecture-experiments.lock') as lock:
  outcomes=[]
  for recipe in RECIPES:
   if args.admission_only and recipe!='baseline':break
   backend=NativeBackend(args.run_id,recipe,lock,resume=args.resume and (C/'insula'/('balanced16-sustained-'+recipe.replace('_','-')+'-'+args.run_id)).exists());statepath=backend.R/'state.json';records=json.loads(statepath.read_text())['records'] if statepath.exists() else []
   if args.admission_only:
    backend.validate_resume(records)
    if len(records)>2 or records and records[-1]['step']>1000:raise ValueError('admission probe never restarts or extends an established trajectory')
    for target in [0,1000]:
     if records and records[-1]['step']>=target:continue
     record=backend.train_and_admit(records[-1] if records else None,target);records.append(record);backend.persist(records)
    decision={'action':'await engineering review','status':'native0/1000 interface admission; no terminal fit or scientific outcome'};backend.persist(records,decision);print('ADMISSION PROBE COMPLETE; full case continuation requires verified source/evidence review',flush=True)
   else:records,decision=execute_case(backend,records)
   outcomes.append({'recipe':recipe,'case_directory':str(backend.R),'manifest_sha256':backend.manifest_sha,'records':records,'decision':decision});write(P/'research'/f'balanced16-sustained-{args.run_id}-progress.json',{'run_id':args.run_id,'cases':outcomes,'complete':not args.admission_only and len(outcomes)==4,'scope':'fixed16 engineering fitting; no heldout scientific promotion','expanded_closure_sha256':sha(closure)})
 print('FINISHED controller invocation',args.run_id,flush=True)
if __name__=='__main__':main()
