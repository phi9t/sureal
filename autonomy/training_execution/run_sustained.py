"""Execute the approved fixed16 one-factor comparison, with live gates throughout."""
import argparse,json,re
from pathlib import Path
P=Path(__file__).resolve().parents[1]
from resources.scientific_payload import sha
from resources.scientific_budget import reserve_write
from resources.backend import ResourceBackend,prepare_identity
from resources.checkpoint import recover_publication_record,resource_inventory,validate_publication_record,write_publication_record
from retention.publication import publish_bundle
from retention.sustained_controller_lock import acquire_experiment_lock
from training_execution.sustained_controller_backend import NativeBackend,publication_matches_record,validate_native_publication_release,write,C,W
from training_execution.sustained_workflow import execute_case
from detection.sustained_contract import RECIPES
from resources.sustained_scoring_budget import stage_timeout
from studies.architecture import experiment_runner

class ResourceNativeBackend(ResourceBackend,NativeBackend):
 resource_launcher_module=experiment_runner
 resource_launcher_path=Path(experiment_runner.__file__).resolve()
 resource_stage_timeout=staticmethod(stage_timeout)
 resource_reserve_write=staticmethod(reserve_write)
 resource_cache_root=C
 resource_work_root=W

 def _recover_native_release(self,record):
  if record.get('released'):return
  candidates=[];incomplete=[]
  for directory in (C/'insula').glob('hdfs-retention-*'):
   publication=directory/'verified-publication.json';release=directory/'release-completed.json'
   if not publication.exists():continue
   try:
    value=json.loads(publication.read_text())
    blob_publication='blobs' in value
    if not blob_publication and not publication_matches_record(record,value):continue
    if release.exists():
     validate_native_publication_release(record,publication,release,completed=True)
     candidates.append((publication,release,value))
    else:
     if blob_publication or isinstance(value.get('release_plan'),list):
      try:validate_native_publication_release(record,publication,None,completed=False)
      except ValueError:incomplete.append(publication)
   except (KeyError,ValueError,OSError,json.JSONDecodeError):
    continue
  if incomplete:raise ValueError('partial native release without durable completion evidence')
  if not candidates:return
  if len(candidates)!=1:raise ValueError('ambiguous native release evidence for resumed record')
  publication,release,value=candidates[0]
  validate_publication_record(self,record)
  identity={'manifest_key':value['blobs']['manifest']['key']} if 'blobs' in value else {'hdfs_manifest_uri':value['publication_manifest_hdfs_uri']}
  record['publication']={'publication_path':str(publication),'publication_sha256':sha(publication),'release_path':str(release),'release_sha256':sha(release),**identity,'command':value.get('command'),'log_sha256':None}
  record['released']=True

 def check_record(self,record,previous):
  self._recover_native_release(record)
  super().check_record(record,previous)
  if record.get('released') or record.get('resource_publication') is not None or (self.resource_root/'checkpoints'/f'checkpoint-{record["target_step"]:02d}-resource-publication.json').exists():
   validate_publication_record(self,record)

 def _ensure_resource_publication(self,record):
  inventory=resource_inventory(self,record)
  recovered=recover_publication_record(self,record,inventory)
  if recovered is not None:return recovered
  receipt=publish_bundle(self,'checkpoint',inventory)
  return write_publication_record(self,record,receipt,inventory)

 def publish_and_release(self,record):
  self.guard();self._ensure_resource_publication(record);validate_publication_record(self,record)
  publication=NativeBackend.publish_and_release(self,record)
  validate_publication_record(self,record)
  return publication

def open_backend(run_id,recipe,lock,*,resume):
 backend=ResourceNativeBackend.__new__(ResourceNativeBackend);backend._resource_identity=None
 NativeBackend.__init__(backend,run_id,recipe,lock,resume=resume)
 identity=backend.R/'resource-layer/identity.json'
 if identity.exists():path,digest=identity,sha(identity)
 else:path,digest=prepare_identity(backend,backend.R/'resource-layer',timeout_for_stage=stage_timeout)
 backend.attach_resources(path,digest)
 return backend

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);parser.add_argument('--resume',action='store_true');parser.add_argument('--admission-only',action='store_true');args=parser.parse_args()
 if re.fullmatch('[A-Za-z0-9]{1,64}',args.run_id) is None:raise ValueError('bounded alphanumeric run ID required')
 results=P/'research/advanced-expanded20261002a-results.json';closure=P/'research/advanced-closure-expanded20261002a-verified.json';evidence=json.loads(closure.read_text());matrix=json.loads(results.read_text())
 if evidence['candidate_sha256']!=sha(results) or evidence['validation']['all_cases_finished'] is not True or len(evidence['validation']['rows'])!=8 or matrix['finished'] is not True or any(sha(path)!=digest for path,digest in evidence['artifacts'].items()):raise ValueError('independent full expanded closure required')
 with acquire_experiment_lock(C/'insula/architecture-experiments.lock') as lock:
  outcomes=[]
  for recipe in RECIPES:
   if args.admission_only and recipe!='baseline':break
   backend=open_backend(args.run_id,recipe,lock,resume=args.resume and (C/'insula'/('balanced16-sustained-'+recipe.replace('_','-')+'-'+args.run_id)).exists());statepath=backend.R/'state.json';records=json.loads(statepath.read_text())['records'] if statepath.exists() else []
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
