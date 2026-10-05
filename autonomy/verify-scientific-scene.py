#!/usr/bin/env python3
"""Live independent native-scene checker on the retained engineering scene."""
import hashlib,json,resource,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from pipeline.insula_entry import launch_plan
from pipeline.runtime_identity import verify_rootfs

HERE=Path(__file__).resolve().parent
CANDIDATES=['pipeline/scientific_scene_validate.py','tests/test_scientific_scene_validate.py','tests/test_scientific_reconstruction.py','pipeline/reconstruction_validate.py','pipeline/scientific_sidecar_reader.py','pipeline/sensor_records.py','pipeline/scientific_reconstruction.py','pipeline/scientific_sidecars.py','pipeline/geometry.py','verify-scientific-scene.py']

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    destination=Path(sys.argv[1]).resolve();destination.mkdir(parents=True,exist_ok=False)
    checked=destination/'checked';checked.mkdir();cache=Path.home()/'.cache/waystone/waymo-perception'
    sidecar_map=json.loads((HERE/'research/scientific-sidecars-evidence.json').read_text());reconstruction_map=json.loads((HERE/'research/scientific-reconstruction-evidence.json').read_text())
    inputs={}
    for label,e in [('sidecars',sidecar_map),('reconstruction',reconstruction_map)]:
        p=Path(e['receipt']);assert sha(p)==e['receipt_sha256'];r=json.loads(p.read_text());base=p.parent
        for name,h in r['artifacts'].items():assert sha(base/name)==h,(label,name)
        inputs[label]={'receipt':str(p),'sha256':sha(p)}
    prepared=Path(sidecar_map['receipt']).parent/'prepared';points=Path(reconstruction_map['receipt']).parent/'produced/points'
    manifest=json.loads((points/'report.json').read_text());hashes=manifest['sidecar_manifest_hashes']
    # Hashes below have already been anchored to the independent sidecar receipt.
    for c,h in hashes.items():assert sha(prepared/c/'manifest.json')==h
    root=cache/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256'])
    source=cache/'slices/validation-two-scenes-20260929';dataset=json.loads((HERE/'dataset.lock.json').read_text());native=next(x for x in dataset['objects'] if x['component']=='lidar' and x['context']==manifest['scene']);assert sha(source/native['relative_path'])==native['sha256']==manifest['source_lidar_sha256']
    candidates={n:sha(HERE/n) for n in CANDIDATES};start=datetime.now(timezone.utc).isoformat();tick=time.monotonic();checks=[]
    commands=[('fixtures',['python','-m','unittest','discover','-s','tests','-p','test_scientific_scene_validate.py','-v']),('native-reconciliation',['python','-c',"import json; from pathlib import Path; from pipeline.scientific_scene_validate import validate_scene; r=validate_scene(Path('/source')/"+repr(native['relative_path'])+",Path('/opt'),Path('/srv'),verified_manifest_hashes="+repr(hashes)+"); Path('/outputs/validation.json').write_text(json.dumps(r,indent=2)); print('PASS independent native scene',r['records'],r['points'],r['scalar_max_error_m'])"])]
    for name,command in commands:
        plan=launch_plan(root,HERE,source,checked,command)
        if name!='fixtures':
            i=plan.index('--');plan[i:i]=['--ro-bind',str(prepared),'/opt','--ro-bind',str(points),'/srv']
        t=time.monotonic();result=subprocess.run(plan,capture_output=True,text=True);(destination/(name+'.log')).write_text(result.stdout+result.stderr);checks.append({'stage':name,'command':plan,'exit_code':result.returncode,'elapsed_seconds':time.monotonic()-t})
        if result.returncode:raise RuntimeError(result.stderr)
    validation=json.loads((checked/'validation.json').read_text());assert validation['points']==manifest['points'] and validation['records']==len(manifest['rows']) and validation['source_lidar_sha256']==native['sha256'];assert validation['report_sha256']==sha(points/'report.json')
    for n,h in candidates.items():assert sha(HERE/n)==h
    for e in inputs.values():assert sha(Path(e['receipt']))==e['sha256']
    receipt={'status':'engineering native scene independently reconciled live','checks':checks,'started_utc':start,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'runtime_lock':lock,'candidate_hashes':candidates,'inputs':inputs,'source_lidar_sha256':native['sha256'],'validation':validation,'artifacts':{str(p.relative_to(destination)):sha(p) for p in destination.rglob('*') if p.is_file()},'scope':'engineering-scene validation of scientific checker; full scientific scene transfer, publication and model comparisons remain open'}
    p=destination/'receipt.json';p.write_text(json.dumps(receipt,indent=2)+'\n');e={'status':'preparation evidence; scientific protocol remains open','receipt':str(p),'receipt_sha256':sha(p),'validation':validation,'scope':receipt['scope']};(HERE/'research/scientific-scene-validation-evidence.json').write_text(json.dumps(e,indent=2)+'\n');print(json.dumps(validation),flush=True)

if __name__=='__main__':main()
