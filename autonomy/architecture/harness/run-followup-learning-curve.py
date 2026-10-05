from pathlib import Path
import datetime,hashlib,json,subprocess,sys,time
code=Path('autonomy').resolve();sys.path.insert(0,str(code))
from pipeline.runtime_identity import verify_rootfs
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
variant=sys.argv[1];assert variant in ['masked_pfn','window_bev','coarse_mlp']
cache=Path.home()/'.cache/waystone/waymo-perception';native=cache/'scientific-processing/overfit-native-cache-v1'
progress_path=code/'research/overfit-native-cache-progress.json';progress=json.loads(progress_path.read_text());assert progress['admitted_frames']==progress['selected_frames']==16
frames=[]
for identity,item in progress['frame_evidence'].items():
 evidence=code/'research'/item['evidence'];assert sha(evidence)==item['evidence_sha256']
 scene,timestamp=identity.split(':');base=native/scene/timestamp;receipt=json.loads((base/'receipt.json').read_text())
 for name,digest in receipt['artifacts'].items():assert sha(base/name)==digest
 frames.append({'identity':identity,'relative_directory':str(Path(scene)/timestamp/'producer'),'sha256':{name:sha(base/'producer'/name) for name in ['observations.npz','targets.npz','report.json']},'receipt_sha256':sha(base/'receipt.json')})
frames=frames[:1] # First preregistered training key, independent of labels/results.
runroot=cache/('insula/architecture-'+variant+'-v1');runroot.mkdir();inputs=runroot/'inputs';inputs.mkdir();output=cache/('scientific-processing/architecture-'+variant+'-v1');output.mkdir()
before_bytes=sum(p.stat().st_size for p in (cache/'scientific-processing').rglob('*') if p.is_file());assert before_bytes+768*1024**2<=15*1024**3
manifest={'architecture_variant':variant,'spec_sha256':sha(Path('docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md')),'followup_spec_sha256':sha(code/'research/architecture-window-control-spec.md'),'scope':'single fixed training-batch overfit; final checkpoint only; no heldout data','progress_sha256':sha(progress_path),'frames':frames,'optimizer':{'lr':1e-4,'betas':[.9,.999],'eps':1e-8,'weight_decay':0,'foreach':False,'gradient_clip':10},'seed':17,'execution':{'updates':2000,'seed':17,'checkpoint_grid':[0,25,50,100,200,300,500,750,1000,1500,2000],'diagnostic_bn':'snapshot/restore all buffers; same training trajectory required','selection':'first admitted fixed training frame, batch size1; no label selection','sampling':'PCG64 seed17 epoch permutation, fixed admitted manifest frame order','loss_gate':'one evaluation-mode frame loss, initial versus final; reduction>=0.8','scoring_gate':'independent native APH on all eligible ROI-center GT, including uncovered boxes; mean populated class APH>=0.8','checkpoint_selection':'final2000 only','deterministic_algorithms':True,'cublas_workspace_config':':4096:8','output_cap_bytes':768*1024**2,'scientific_working_cap_bytes':15*1024**3}}
(inputs/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
old=json.loads((cache/'detector-gpu-live-a/receipt.json').read_text());lock=old['runtime_lock']
print('VERIFY locked GPU runtime',flush=True);verify_rootfs(cache/'gpu-rootfs',lock['rootfs_sha256'])
for path,digest in old['driver_hashes'].items():assert sha(path)==digest
command=old['checks'][0]['command'].copy();command=[str(output) if x==str(cache/'detector-gpu-live-a') else '/experiment/gpu/native-followup-learning-curve.py' if x=='/experiment/gpu/detector-probe.py' else x for x in command]
separator=command.index('--');command[separator:separator]=['--setenv','CUBLAS_WORKSPACE_CONFIG',':4096:8'];separator=command.index('--');command[separator:separator]=['--ro-bind',str(native),'/tmp/native','--ro-bind',str(inputs),'/tmp/inputs']
pins={str(p.relative_to(code)):sha(p) for p in [code/'gpu/native-followup-learning-curve.py',code/'gpu/architecture_variants.py',code/'gpu/architecture_followups.py',code/'gpu/norm_variants.py',*sorted((code/'pipeline').glob('*.py'))]}
started=datetime.datetime.now(datetime.timezone.utc).isoformat();tick=time.monotonic();print('RUN fixed native overfit',flush=True)
(code/('research/architecture-'+variant+'-execution-pending.json')).write_text(json.dumps({'started_utc':started,'command':command,'candidate_hashes':pins,'manifest':manifest,'manifest_sha256':sha(inputs/'manifest.json'),'scope':'preregistered single fixed training-batch overfit only; no heldout comparison'},indent=2)+'\n')
with (output/'live.log').open('w') as log:run=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,text=True,timeout=7200)
print((output/'live.log').read_text(),flush=True);assert run.returncode==0
assert all(sha(code/p)==h for p,h in pins.items())
assert sum(p.stat().st_size for p in output.rglob('*') if p.is_file())<=768*1024**2
assert sum(p.stat().st_size for p in (cache/'scientific-processing').rglob('*') if p.is_file())<=15*1024**3
record={'started_utc':started,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'live_seconds':time.monotonic()-tick,'checks':[{'command':command,'exit_code':run.returncode}],'runtime_lock':lock,'driver_hashes':old['driver_hashes'],'candidate_hashes':pins,'manifest_sha256':sha(inputs/'manifest.json'),'manifest':manifest,'validation':json.loads((output/'check.json').read_text()),'artifacts':{str(p):sha(p) for p in output.rglob('*') if p.is_file()},'scope':'single fixed training-batch overfit execution; independent scoring/admission still required; main-study gates remain open'}
(code/('research/architecture-'+variant+'-execution-verified.json')).write_text(json.dumps(record,indent=2)+'\n')
print('RECORDED native overfit execution',flush=True)
