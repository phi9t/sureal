"""Frozen native selected-frame packing and independent all-anchor audit."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
from pipeline.insula_entry import launch_plan
from pipeline.runtime_identity import verify_rootfs
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
C=Path.home()/'.cache/waystone/waymo-perception';W=C/'scientific-processing';base=W/'balanced16-native-v2';base.mkdir();run=C/'insula/balanced16-native-v2';run.mkdir();snapshot=run/'source';snapshot.mkdir();shutil.copytree(P/'pipeline',snapshot/'pipeline',ignore=shutil.ignore_patterns('__pycache__'));shutil.copytree(P/'cohort',snapshot/'cohort',ignore=shutil.ignore_patterns('__pycache__'));pins={str(p):sha(p) for p in snapshot.rglob('*') if p.is_file()}
root=C/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256'])
selection=json.loads((P/'research/balanced16-selection.candidate.json').read_text());proof=json.loads((P/'research/balanced16-physical-v3-progress.json').read_text());assert proof['admitted_scenes']==13
labelproof=json.loads((P/'research/balanced16-labels-and-anchor-coverage-v3-verified.json').read_text());assert labelproof['label_and_anchor_coverage_gate_passed']
jobtemplate=json.loads(next((W/'overfit-native-cache-v1').glob('*/*/input/job.json')).read_text());done={}
for frame in selection['frames']:
 scene,t=frame['identity'].split(':');t=int(t);e=next(x for x in proof['scene_receipts'] if x['scene']==scene);assert sha(e['receipt'])==e['sha256'];physical=W/'balanced16-physical-v2'/scene/'producer';boxes=W/'balanced16-labels-v2'/scene/'producer';d=base/scene/str(t);d.mkdir(parents=True);inp=d/'input';inp.mkdir();job={**jobtemplate,'scene':scene,'timestamp_micros':t,'physical_file':f'{t}.npz','physical_sha256':sha(physical/f'{t}.npz'),'box_report_sha256':sha(boxes/'targets.json'),'packing_seed':int.from_bytes(hashlib.sha256(frame['identity'].encode()).digest()[:8],'big')};(inp/'job.json').write_text(json.dumps(job));checks=[]
 assert sum(p.stat().st_size for p in W.rglob('*') if p.is_file())+100*1024**2<15*1024**3
 for mode,worker in [('producer','prepare-overfit-native-frame-v3.py'),('reference','overfit-native-cache-audit.py')]:
  out=d/mode;out.mkdir();cmd=launch_plan(root,snapshot,physical,out,['python','/tmp/workers/'+worker]);i=cmd.index('--');cmd[i:i]=['--ro-bind',str(snapshot/'cohort'),'/tmp/workers','--ro-bind',str(inp),'/tmp/input','--ro-bind',str(boxes),'/tmp/boxes',*(['--ro-bind',str(d/'producer'),'/tmp/prepared'] if mode=='reference' else [])];r=subprocess.run(cmd,capture_output=True,text=True,timeout=300);(out/'live.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr;checks.append({'command':cmd,'exit_code':0})
 assert all(sha(p)==h for p,h in pins.items());receipt={'checks':checks,'source_pins':pins,'runtime_lock':lock,'physical_admission':e,'artifacts':{str(p.relative_to(d)):sha(p) for p in d.rglob('*') if p.is_file()},'validation':json.loads((d/'reference/check.json').read_text())};(d/'receipt.json').write_text(json.dumps(receipt,indent=2));done[frame['identity']]={'receipt':str(d/'receipt.json'),'sha256':sha(d/'receipt.json'),'validation':receipt['validation']};(P/'research/balanced16-native-progress.json').write_text(json.dumps({'frame_evidence':done,'expected_frames':16,'admitted_frames':len(done)},indent=2));print('ADMITTED BALANCED NATIVE',len(done),frame['identity'],flush=True)
