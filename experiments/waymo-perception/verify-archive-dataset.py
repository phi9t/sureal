#!/usr/bin/env python3
"""Replay the engineering HDFS archive twice against verified native point files."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from pipeline.insula_entry import launch_plan
from pipeline.runtime_identity import verify_rootfs

REPLAY = '''import json,hashlib
from pathlib import Path
import numpy as np
from pipeline.scientific_dataset import iter_scene_records
reference=json.loads(Path('/opt/report.json').read_text())
expected={(r['context'],r['timestamp'],r['laser'],r['return']):r for r in reference['rows']}
seen=set(); digest=hashlib.sha256(); points=0
for row in iter_scene_records(Path('/source/scene.tar'),Path('/source/publication.json'),expected_publication_sha256=PUBLICATION_HASH,usage='engineering'):
 identity=row['identity']; key=tuple(identity[k] for k in ('context','timestamp','laser','return'))
 assert key in expected and key not in seen; seen.add(key); r=expected[key]
 assert row['return_present']==r['return_present']
 path=Path('/opt')/r['artifact']; assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256']
 assert set(row['observations'])=={'xyz','physical_features'}
 assert set(row['evaluation'])=={'nlz'} and set(row['correspondence'])=={'camera_projection'}
 assert ('segmentation' in row['targets'])==r['segmentation_present'] and identity['motion']==r['motion']
 actual={**row['observations'],**row['evaluation'],**row['correspondence'],**row['targets'],'pixels':identity['pixels']}
 with np.load(path,allow_pickle=False) as old:
  assert set(actual)==set(old.files); digest.update(json.dumps(key).encode())
  for name in sorted(actual):
   assert actual[name].dtype==old[name].dtype and np.array_equal(actual[name],old[name],equal_nan=True),(key,name)
   digest.update(name.encode()); digest.update(str(actual[name].dtype).encode()); digest.update(actual[name].tobytes())
 points+=r['points']
assert seen==set(expected)
Path('/outputs/replay.json').write_text(json.dumps({'records':len(seen),'points':points,'identity_array_digest':digest.hexdigest(),'status':'all returned arrays independently match verified source point records'}))
print('PASS independent dataset replay',len(seen),points)
'''


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base=Path(sys.argv[1]).resolve();base.mkdir(parents=True,exist_ok=False)
    cache=Path.home()/'.cache/waystone/waymo-perception'
    published=cache/'insula/scene-archive-hdfs-live-a'
    evidence=json.loads((HERE/'research/scene-archive-hdfs-evidence.json').read_text())
    if sha(published/'receipt.json')!=evidence['receipt_sha256']:raise ValueError('publication receipt changed')
    prior=json.loads((published/'receipt.json').read_text());expected=prior['artifacts']['packed/publication.json']
    if sha(published/'checked/publication-roundtrip.json')!=expected:raise ValueError('downloaded publication differs')
    reference=cache/'insula/scientific-reconstruction-live-a/produced/points'
    refreceipt=reference.parent.parent/'receipt.json';ref=json.loads(refreceipt.read_text())
    refevidence=json.loads((HERE/'research/scientific-reconstruction-evidence.json').read_text())
    if sha(refreceipt)!=refevidence['receipt_sha256'] or sha(reference/'report.json')!=ref['artifacts']['produced/points/report.json']:
        raise ValueError('independent reconstruction reference changed')
    root=cache/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256'])
    names=['verify-archive-dataset.py','pipeline/scientific_dataset.py','pipeline/scene_archive_validate.py','tests/test_scientific_dataset.py']
    candidates={p:sha(HERE/p) for p in names};checks=[];outputs=[]
    start=datetime.now(timezone.utc).isoformat();tick=time.monotonic()
    for index in range(3):
        out=base/('fixtures' if index==0 else f'replay-{index}');out.mkdir();outputs.append(out)
        command=['python','-m','unittest','discover','-s','tests','-p','test_scientific_dataset.py','-v'] if index==0 else ['python','-c','PUBLICATION_HASH='+repr(expected)+'\n'+REPLAY]
        plan=launch_plan(root,HERE,published/'packed',out,command)
        if index:
            i=plan.index('--');plan[i:i]=['--ro-bind',str(reference),'/opt']
        stage_start=datetime.now(timezone.utc).isoformat();t=time.monotonic();result=subprocess.run(plan,capture_output=True,text=True)
        (base/(out.name+'.log')).write_text(result.stdout+result.stderr)
        checks.append({'stage':out.name,'command':plan,'started_utc':stage_start,'ended_utc':datetime.now(timezone.utc).isoformat(),'exit_code':result.returncode,'elapsed_seconds':time.monotonic()-t})
        print(out.name,result.returncode,result.stdout.strip(),flush=True)
        if result.returncode:raise RuntimeError(result.stderr)
    a=json.loads((outputs[1]/'replay.json').read_text());b=json.loads((outputs[2]/'replay.json').read_text())
    if a!=b or a['records']!=1980 or a['points']!=36214548:raise ValueError('engineering replay identity/support differs')
    for name,digest in candidates.items():
        if sha(HERE/name)!=digest:raise ValueError('candidate changed during replay')
    receipt={'status':'two independent live dataset replays match verified source arrays','checks':checks,'started_utc':start,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'runtime_lock':lock,'candidate_hashes':candidates,'publication_receipt_sha256':sha(published/'receipt.json'),'reference_receipt_sha256':sha(refreceipt),'publication_manifest_sha256':expected,'validation':a,'artifacts':{str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()},'prior_failures':[{'log':str(cache/'insula/scientific-dataset-live-a/replay-1.log'),'reason':'initial loader incorrectly required integer projection storage dtype'},{'log':str(cache/'insula/scientific-dataset-live-b/replay-1.log'),'reason':'initial loader rejected native instance -1 with valid stuff semantics'}],'scope':'two full engineering-scene archive replays; scientific cohort loader admission/protocol and model outcomes remain open'}
    (base/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    summary={'status':'preparation evidence; no scientific gate closure','receipt':str(base/'receipt.json'),'receipt_sha256':sha(base/'receipt.json'),'validation':a,'scope':receipt['scope']}
    (HERE/'research/scientific-dataset-evidence.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('PASS verified engineering archive dataset evidence')


if __name__=='__main__':main()
