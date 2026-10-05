"""Independent retained physical replay against a frozen source dependency bundle."""
import hashlib,json,resource,shutil,subprocess,sys,tempfile
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PACKAGE))
from pipeline.insula_entry import launch_plan
from pipeline.runtime_identity import verify_rootfs
from pipeline.source_integrity import verify_source
from pipeline.staging_lease import staging_lease
from pipeline.training_box_replay import retained_raw_bytes
from pipeline.scientific_admission import check_raw_capacity
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cache=Path.home()/'.cache/waystone/waymo-perception';root=cache/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256']);progress=json.loads((PACKAGE/'research/balanced16-physical-progress.json').read_text());assert progress['admitted_scenes']==13
base=cache/'insula/balanced16-physical-readmission-v3';base.mkdir();package=base/'source/autonomy';package.mkdir(parents=True);shutil.copytree(PACKAGE/'pipeline',package/'pipeline',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));(package/'cohort').mkdir();shutil.copyfile(PACKAGE/'cohort/raw_reconstruct_v3.py',package/'cohort/raw_reconstruct.py');pins={str(p.relative_to(package)):sha(p) for p in package.rglob('*') if p.is_file()};(base/'source-pins.json').write_text(json.dumps(pins,indent=2));retained=retained_raw_bytes(cache,PACKAGE);admitted=[]
for entry in progress['scene_receipts']:
 original=Path(entry['receipt']);assert sha(original)==entry['sha256'];old=json.loads(original.read_text())
 for p,h in old['artifacts'].items():assert sha(p)==h
 job=json.loads((original.parent/'input/job.json').read_text());size=sum(int(r['source_metadata']['size']) for r in job['sources'].values());check_raw_capacity(retained,size,2*1024**3,active_objects=0);directory=base/entry['scene'];directory.mkdir();inputs=directory/'input';inputs.mkdir();(inputs/'job.json').write_text(json.dumps(job,indent=2));transfers=[]
 with staging_lease(cache/'raw-staging.lock'),tempfile.TemporaryDirectory(dir=cache/'scientific-processing-staging',prefix='stage-') as tmp:
  staged=Path(tmp)
  for component,r in job['sources'].items():
   path=staged/(component+'.parquet');command=['timeout','--kill-after=5s','120s','bash',str(PACKAGE/'gcs.sh'),'--','storage','cp',r['source_metadata']['storage_url'],str(path)]
   remaining=2*1024**3-retained-sum(p.stat().st_size for p in staged.iterdir() if p.is_file())
   def cap():resource.setrlimit(resource.RLIMIT_FSIZE,(remaining,remaining))
   result=subprocess.run(command,capture_output=True,text=True,preexec_fn=cap);assert result.returncode==0,(component,result.stderr);transfers.append({'command':command,'exit_code':0,'verification':verify_source(path,size_bytes=int(r['source_metadata']['size']),sha256=r['sha256'],md5_base64=r['source_metadata']['md5_hash'])})
  out=directory/'output';out.mkdir();command=launch_plan(root,package,staged,out,['python','/experiment/cohort/raw_reconstruct.py','reference']);i=command.index('--');command[i:i]=['--ro-bind',str(inputs),'/tmp/input','--ro-bind',str(original.parent/'producer'),'/tmp/produced'];run=subprocess.run(command,capture_output=True,text=True,timeout=600);(out/'live.log').write_text(run.stdout+run.stderr);assert run.returncode==0,(entry['scene'],run.stderr)
 assert all(sha(package/p)==h for p,h in pins.items())
 for p,h in old['artifacts'].items():assert sha(p)==h
 receipt={'checks':[{'command':command,'exit_code':0}],'runtime_lock':lock,'source_snapshot':str(package),'candidate_hashes':pins,'original_producer_receipt_sha256':sha(original),'original_producer_receipt':str(original),'transfers':transfers,'validation':json.loads((out/'check.json').read_text()),'artifacts':{str(p):sha(p) for p in out.iterdir()},'scope':'independent full identity/intensity/NLZ and exact vector replay; up to17 independent scalar XYZ checks per return; frozen dependency bundle'};(directory/'receipt.json').write_text(json.dumps(receipt,indent=2));admitted.append({'scene':entry['scene'],'receipt':str(directory/'receipt.json'),'sha256':sha(directory/'receipt.json')});(PACKAGE/'research/balanced16-physical-v3-progress.json').write_text(json.dumps({'expected_scenes':13,'admitted_scenes':len(admitted),'scene_receipts':admitted,'source_snapshot':str(package),'candidate_hashes':pins},indent=2)+'\n');print('STRICTLY ADMITTED PHYSICAL',entry['scene'],flush=True)
