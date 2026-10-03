"""Recover only terminal native scoring after a confirmed pilot score timeout.

Preserves original frozen code, failed output, checkpoints, exports and receipts.
Only the two native subprocess bounds change, 600 -> 1800 seconds, in a new
pinned code snapshot. Training budgets, predictions, GT and metric config do not.
"""
import argparse,fcntl,hashlib,json,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
from pipeline.insula_entry import launch_plan
from pipeline.runtime_identity import verify_rootfs
C=Path.home()/'.cache/waystone/waymo-perception'
def sha(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);a=parser.parse_args()
 import re
 if re.fullmatch('[A-Za-z0-9]{1,64}',a.run_id) is None:raise ValueError('safe run ID required')
 lock=(C/'insula/architecture-experiments.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 original=C/'insula/balanced16-sustained-admission-native20261003a';failed=original/'scored-35/live.log'
 if 'timed out after 600 seconds' not in failed.read_text() or (original/'score-35-verified.json').exists():raise ValueError('confirmed failed native score required')
 steps=[0,19,35];names=['train','audit','literal-loss','export','proposals','score','metrics-audit'];parents={}
 for step in steps:
  for name in names:
   key=f'{name}-{step}'
   if step==35 and name in ['score','metrics-audit']:continue
   path=original/(key+'-verified.json');record=json.loads(path.read_text())
   if record['stage']!=key or record['exit_code']!=0:raise ValueError('prior stage not admitted')
   for p,digest in record['artifacts'].items():
    if sha(p)!=digest:raise ValueError('original stage artifact changed')
   parents[key]={'path':str(path),'sha256':sha(path)}
 manifest=original/'input/manifest.json';frozen=json.loads(manifest.read_text());oldcode=original/'code'
 for name,digest in frozen['source_hashes'].items():
  if sha(oldcode/name)!=digest:raise ValueError('original frozen package changed')
 R=C/'insula'/('balanced16-scoring-recovery-'+a.run_id);R.mkdir();code=R/'code';shutil.copytree(oldcode,code);changes={}
 for name in ['metrics_sustained_v3.py','audit_metrics_sustained_v3.py']:
  path=code/'cohort'/name;before=path.read_text()
  if before.count('timeout=600')!=1:raise ValueError('exact native timeout site required')
  path.write_text(before.replace('timeout=600','timeout=1800'))
  changes[name]={'original_sha256':sha(oldcode/'cohort'/name),'recovery_sha256':sha(path),'only_change':'native subprocess timeout=600 -> timeout=1800'}
 pins={str(p.relative_to(code)):sha(p) for p in code.rglob('*.py')};host_sha=sha(__file__)
 root=C/'metrics-rootfs';runtime=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,runtime['rootfs_sha256']);prepared=original/'prepared-35';export=json.loads((original/'export-35-verified.json').read_text());source=R/'input';source.mkdir();shutil.copyfile(manifest,source/'manifest.json')
 def stage(name,worker,extra):
  inputdir=R/(name+'-input');shutil.copytree(source,inputdir);inputpins={str(p):sha(p) for p in inputdir.iterdir()};out=R/name;out.mkdir();command=launch_plan(root,code,prepared,out,['python','/experiment/cohort/'+worker]);at=command.index('--');command[at:at]=extra(inputdir);started=time.monotonic()
  result=subprocess.run(command,capture_output=True,text=True,timeout=2100);(out/'live.log').write_text(result.stdout+result.stderr)
  if result.returncode:raise RuntimeError('recovery stage failed; retained '+str(out/'live.log'))
  if sha(__file__)!=host_sha or any(sha(code/name)!=digest for name,digest in pins.items()) or any(sha(p)!=h for p,h in inputpins.items()):raise ValueError('host/worker/input changed')
  receipt={'stage':name,'command':command,'exit_code':0,'source_hashes':pins,'host_sha256':host_sha,'runtime_lock':runtime,'manifest_sha256':sha(manifest),'original_failed_log_sha256':sha(failed),'original_parents':parents,'recovery_changes':changes,'input_hashes':inputpins,'parent_artifacts':export['artifacts'],'artifacts':{str(p):sha(p) for p in out.iterdir()},'validation':json.loads((out/'check.json').read_text()),'elapsed_seconds':time.monotonic()-started,'scope':'terminal35 native scoring recovery only; unchanged full16 V3 predictions/GT/native config; no training replay or fit promotion'}
  path=R/(name+'-verified.json');path.write_text(json.dumps(receipt,indent=2)+'\n');print('ADMITTED',name,flush=True);return receipt,path,out
 score,scorepath,scored=stage('score-35','metrics_sustained_v3.py',lambda _:[])
 (source/'score-receipt.json').write_bytes(scorepath.read_bytes());(source/'expected.json').write_text(json.dumps({'receipt':score,'receipt_sha256':sha(scorepath)}))
 audit,auditpath,_=stage('metrics-audit-35','audit_metrics_sustained_v3.py',lambda inp:['--ro-bind',str(scored),'/tmp/scored','--ro-bind',str(inp/'score-receipt.json'),'/tmp/score-receipt.json','--ro-bind',str(inp/'expected.json'),'/tmp/expected.json'])
 parents.update({'score-35':{'path':str(scorepath),'sha256':sha(scorepath)},'metrics-audit-35':{'path':str(auditpath),'sha256':sha(auditpath)}})
 final={'run_directory':str(original),'recovery_directory':str(R),'output_directory':str(C/'scientific-processing/balanced16-sustained-admission-native20261003a'),'manifest_sha256':sha(manifest),'stage_receipts':parents,'recovery_changes':changes,'original_failure_sha256':sha(failed),'scope':'recovered native baseline0/19/35 engineering pilot; independent review/retention required; no sustained fit or scientific acceptance'}
 (P/'research'/f'balanced16-sustained-admission-{a.run_id}-recovered.json').write_text(json.dumps(final,indent=2)+'\n');print('PASS recovered terminal scoring and independent native replay',flush=True)
if __name__=='__main__':main()
