#!/usr/bin/env python3
"""Two live scientific camera replays against externally verified native sidecars."""
import argparse,json,resource,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from evidence.source_snapshot import file_sha256 as sha
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
HERE=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('processing',type=Path);p.add_argument('publication',type=Path);p.add_argument('output',type=Path);p.add_argument('--expected-receipt-sha256',required=True);p.add_argument('--usage',required=True);args=p.parse_args();processing=args.processing.resolve();publication=args.publication.resolve();base=args.output.resolve();pp=publication/'receipt.json'
 if sha(pp)!=args.expected_receipt_sha256:raise ValueError('trusted camera publication receipt differs')
 pub=json.loads(pp.read_text())
 for n,h in pub['candidate_hashes'].items():
  if sha(HERE/n)!=h:raise ValueError('camera publication candidate changed')
 for n,h in pub['artifacts'].items():
  if sha(publication/n)!=h:raise ValueError('camera publication artifact changed')
 references={}
 for component,h in pub['component_receipt_hashes'].items():
  cp=processing/'evidence'/component/'receipt.json'
  if sha(cp)!=h:raise ValueError('trusted original camera receipt differs')
  r=json.loads(cp.read_text())
  for n,v in r['artifacts'].items():
   if sha(processing/n)!=v:raise ValueError('original camera artifact differs')
  references[component]=r['artifacts']['sidecars/'+component+'/manifest.json']
 cache=Path.home()/'.cache/waystone/waymo-perception';root=cache/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256']);base.mkdir(parents=True,exist_ok=False);inputs=base/'input';inputs.mkdir();(inputs/'reference.json').write_text(json.dumps(references)+'\n');checks=[];results=[];started=datetime.now(timezone.utc).isoformat();tick=time.monotonic();names=['camera/verify-camera-replay.py','camera/camera_replay_check.py','camera/camera_dataset.py','dataset/component_archive_validate.py'];candidates={n:sha(HERE/n) for n in names}
 for index in (1,2):
  out=base/f'replay-{index}';out.mkdir();cmd=['python','-m','camera.camera_replay_check','--publication-sha',pub['publication_manifest_sha256'],'--usage',args.usage];plan=launch_plan(root,HERE,publication/'packed',out,cmd);i=plan.index('--');plan[i:i]=['--ro-bind',str(processing/'sidecars'),'/opt','--ro-bind',str(inputs),'/mnt'];t=time.monotonic();r=subprocess.run(plan,capture_output=True,text=True);(base/f'replay-{index}.log').write_text(r.stdout+r.stderr);checks.append({'stage':f'replay-{index}','command':plan,'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-t})
  if r.returncode:raise RuntimeError(r.stderr)
  results.append(json.loads((out/'replay.json').read_text()));print('PASS scientific camera replay',index,results[-1]['rows'],flush=True)
 if results[0]!=results[1]:raise ValueError('camera replays differ')
 for n,h in candidates.items():
  if sha(HERE/n)!=h:raise ValueError('camera replay candidate changed')
 if sha(pp)!=args.expected_receipt_sha256:raise ValueError('camera publication identity changed')
 receipt={'status':'two scientific camera native-record replays independently checked live','scene':pub['scene'],'usage':args.usage,'publication_receipt_sha256':args.expected_receipt_sha256,'checks':checks,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'candidate_hashes':candidates,'runtime_lock':lock,'validation':results[0],'artifacts':{str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()},'scope':'one scientific camera scene; task models, class mapping, full cohort and protocol remain open'};(base/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS scientific camera replay receipt',flush=True)
if __name__=='__main__':main()
