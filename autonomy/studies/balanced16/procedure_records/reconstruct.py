"""Acquire a small hash-pinned native slice via GCS; HDFS mirror identities preserved."""
import hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PACKAGE))
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from dataset.source_integrity import verify_source
from insula.staging_lease import staging_lease
from detection.training_box_replay import retained_raw_bytes
from dataset.scientific_admission import check_raw_capacity
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cache=Path.home()/'.cache/waystone/waymo-perception';root=cache/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256']);candidate_path=PACKAGE/'research/balanced16-selection.candidate.json';candidate=json.loads(candidate_path.read_text());candidate_sha=sha(candidate_path);worker=PACKAGE/'cohort/raw_reconstruct.py';digest=sha(worker);destination=cache/'scientific-processing/balanced16-physical-v2';destination.mkdir();retained=retained_raw_bytes(cache,PACKAGE);complete=[]
for scene in sorted({f['identity'].split(':')[0] for f in candidate['frames']}):
 frames=[f for f in candidate['frames'] if f['identity'].split(':')[0]==scene];records={c:json.loads((cache/'scientific-source-audit'/f'training-{c}-{scene}.json').read_text()) for c in ['lidar','lidar_calibration','vehicle_pose','lidar_pose']};size=sum(int(r['source_metadata']['size']) for r in records.values());check_raw_capacity(retained,size,2*1024**3,active_objects=0);base=destination/scene;base.mkdir();inputs=base/'input';inputs.mkdir();job={'scene':scene,'timestamps':[int(f['identity'].split(':')[1]) for f in frames],'sources':records};(inputs/'job.json').write_text(json.dumps(job,indent=2));checks=[];transfers=[]
 with staging_lease(cache/'raw-staging.lock'),tempfile.TemporaryDirectory(dir=cache/'scientific-processing-staging',prefix='stage-') as tmp:
  staged=Path(tmp)
  for component,r in records.items():
   path=staged/(component+'.parquet');command=['timeout','--kill-after=5s','120s','bash',str(PACKAGE/'dataset/gcs.sh'),'--','storage','cp',r['source_metadata']['storage_url'],str(path)];result=subprocess.run(command,capture_output=True,text=True);assert result.returncode==0,(component,result.stderr);transfers.append({'command':command,'exit_code':0,'verification':verify_source(path,size_bytes=int(r['source_metadata']['size']),sha256=r['sha256'],md5_base64=r['source_metadata']['md5_hash'])})
  for mode in ['producer','reference']:
   out=base/mode;out.mkdir();command=launch_plan(root,PACKAGE,staged,out,['python','/tmp/worker.py',mode]);i=command.index('--');command[i:i]=['--ro-bind',str(worker),'/tmp/worker.py','--ro-bind',str(inputs),'/tmp/input',*(['--ro-bind',str(base/'producer'),'/tmp/produced'] if mode=='reference' else [])];run=subprocess.run(command,capture_output=True,text=True,timeout=600);(out/'live.log').write_text(run.stdout+run.stderr);assert run.returncode==0,(scene,mode,run.stderr);checks.append({'command':command,'exit_code':0})
 assert sha(worker)==digest and sha(candidate_path)==candidate_sha
 receipt={'checks':checks,'runtime_lock':lock,'selection_sha256':candidate_sha,'worker_sha256':digest,'transfers':transfers,'native_source_receipts_sha256':{c:sha(cache/'scientific-source-audit'/f'training-{c}-{scene}.json') for c in records},'artifacts':{str(p):sha(p) for p in base.rglob('*') if p.is_file()},'validation':json.loads((base/'reference/check.json').read_text()),'scope':'small selected physical slice independently checked; source generations equal admitted HDFS mirrors; no packing or quality acceptance'};(base/'receipt.json').write_text(json.dumps(receipt,indent=2));complete.append({'scene':scene,'receipt':str(base/'receipt.json'),'sha256':sha(base/'receipt.json')});(PACKAGE/'research/balanced16-physical-progress.json').write_text(json.dumps({'expected_scenes':13,'admitted_scenes':len(complete),'scene_receipts':complete},indent=2)+'\n');print('ADMITTED PHYSICAL',scene,flush=True)
print('COMPLETE selected sensor slice',len(complete),flush=True)
