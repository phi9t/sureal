"""Independently replay every balanced-fixture target inside live Insula."""
import hashlib,json,subprocess,sys
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PACKAGE))
from insula.entry import launch_plan
from admissions import validate_coverage_claim
from insula.runtime_identity import verify_rootfs
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cache=Path.home()/'.cache/waystone/waymo-perception';root=cache/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256']);record=PACKAGE/'research/balanced16-labels-and-anchor-coverage.json';d=json.loads(record.read_text());worker=PACKAGE/'cohort/audit_targets_v2.py';digest=sha(worker);base=cache/'insula/balanced16-labels-audit-v3';base.mkdir();checks=[];validation=[]
for scene in d['scene_receipts']:
 receipt=Path(scene['receipt']);assert sha(receipt)==scene['sha256'];r=json.loads(receipt.read_text())
 for p,h in r['artifacts'].items():assert sha(p)==h
 directory=receipt.parent;out=base/scene['scene'];out.mkdir();command=launch_plan(root,PACKAGE,directory/'targets',out,['python','/tmp/worker.py']);i=command.index('--');command[i:i]=['--ro-bind',str(worker),'/tmp/worker.py','--ro-bind',str(directory/'input'),'/tmp/input','--ro-bind',str(directory/'producer'),'/tmp/boxes'];run=subprocess.run(command,capture_output=True,text=True,timeout=180);(out/'live.log').write_text(run.stdout+run.stderr);assert run.returncode==0,(scene['scene'],run.stderr);checks.append({'command':command,'exit_code':0});validation.extend(json.loads((out/'check.json').read_text())['frames']);print('ADMITTED TARGET AUDIT',scene['scene'],flush=True)
 for p,h in r['artifacts'].items():assert sha(p)==h
assert len(validation)==16 and sha(worker)==digest
covered=validate_coverage_claim(d['covered_object_coverage'],validation);passed=True;result={'checks':checks,'runtime_lock':lock,'worker_sha256':digest,'producer_receipt_sha256':sha(record),'validation':validation,'positive_anchor_covered_object_coverage':covered,'label_and_anchor_coverage_gate_passed':passed,'artifacts':{str(p):sha(p) for p in base.rglob('*') if p.is_file()},'scope':'native labels and literal anchor coverage independently admitted; physical measurement support and quality remain open'};(PACKAGE/'research/balanced16-labels-and-anchor-coverage-v3-verified.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS label/anchor coverage',passed,covered)
