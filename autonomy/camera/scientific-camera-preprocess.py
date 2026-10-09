#!/usr/bin/env python3
"""Stage scientific camera sources and independently retain original native rows."""
import argparse,json,resource,time
from datetime import datetime,timezone
from pathlib import Path
from insula.launch_plan import build_plan, load_default_runtime_lock, record_plan, run_plan
from insula.runtime_roots import current_cpu_rootfs
from evidence.source_snapshot import file_sha256 as sha
from dataset.scientific_admission import admit_scene
from dataset.staged_source import staged_source
from resources.scientific_budget import SCIENTIFIC_WORKING_CAP_BYTES
HERE=Path(__file__).resolve().parents[1]
COMPONENTS=['camera_image','camera_segmentation','camera_box']
CANDIDATES=['camera/scientific-camera-preprocess.py','camera/camera_sidecars.py','camera/camera_sidecar_validate.py','dataset/scientific_admission.py','dataset/staged_source.py','insula/staging_lease.py','dataset/source_integrity.py','insula/launch_plan.py','insula/runtime_roots.py','resources/scientific_budget.py']
def total(root):return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--scene',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 cache=Path.home()/'.cache/waystone/waymo-perception';working=cache/'scientific-processing';destination=args.output.resolve()
 if working.resolve() not in destination.parents:raise ValueError('scientific camera output must remain within accounted working root')
 manifest=json.loads((HERE/'dataset/scientific-acquisition.candidate.json').read_text());manifest['excluded_engineering_segments']=json.loads((HERE/'dataset/scientific-cohort.candidate.json').read_text())['excluded_engineering_segments'];group=manifest['scenes'][args.scene]
 paths={c:cache/'scientific-source-audit'/f"{group['official_split']}-{c}-{args.scene}.json" for c in manifest['components']};records={c:json.loads(p.read_text()) for c,p in paths.items()};admitted=admit_scene(manifest,records,args.scene)
 runtime=load_default_runtime_lock(current_cpu_rootfs(cache));lock=runtime.data
 candidates={n:sha(HERE/n) for n in CANDIDATES};source_identities={c:sha(p) for c,p in paths.items()};retained=sum(o['size_bytes'] for o in json.loads((HERE/'dataset/dataset.lock.json').read_text())['objects']);limit=SCIENTIFIC_WORKING_CAP_BYTES
 destination.mkdir(parents=True,exist_ok=True)
 for component in COMPONENTS:
  base=destination/'evidence'/component;prepared=destination/'sidecars';decoded=prepared/component;receipt_path=base/'receipt.json';record=admitted['components'][component]
  if receipt_path.exists():
   previous=json.loads(receipt_path.read_text())
   if previous['candidate_hashes']!=candidates or previous['source_record_sha256']!=source_identities[component] or previous['runtime_lock']!=lock or any(c['exit_code'] for c in previous['checks']):raise ValueError('camera resume identities differ')
   for n,h in previous['artifacts'].items():
    if sha(destination/n)!=h:raise ValueError('camera resume artifact differs')
   print('verified camera resume',component,flush=True);continue
  if base.exists() or decoded.exists():raise ValueError('preserve unpromoted partial camera output')
  remaining=limit-total(working)
  if remaining<=0:raise ValueError('combined scientific working-set exhausted')
  base.mkdir(parents=True);prepared.mkdir(exist_ok=True);checked=base/'checked';checked.mkdir();checks=[];started=datetime.now(timezone.utc).isoformat();tick=time.monotonic()
  with staged_source(record,cache,retained_bytes=retained,limit_bytes=manifest['local_staging_limit_bytes']) as (source,transfer):
   produce="from camera.camera_sidecars import materialize_camera_component; r=materialize_camera_component('/source/source.parquet',"+repr(component)+","+repr(args.scene)+",'/outputs/"+component+"',"+str(remaining)+"); print('PASS native camera rows',len(r['rows']))"
   check="import json; from pathlib import Path; from camera.camera_sidecar_validate import validate_camera_component; r=validate_camera_component('/source/source.parquet','/opt/"+component+"'); Path('/outputs/check.json').write_text(json.dumps(r)); print('PASS independent native camera rows',r['rows'])"
   for name,out,code in [('decode',prepared,produce),('independent-check',checked,check)]:
    named_inputs={'/opt':prepared} if name=='independent-check' else None
    plan=build_plan(runtime,code=HERE,source=source.parent,output=out,command=['python','-c',code],named_inputs=named_inputs)
    before=time.monotonic();r=run_plan(plan,capture_output=True,text=True);(base/(name+'.log')).write_text(r.stdout+r.stderr);checks.append({'stage':name,'launch_plan':record_plan(plan),'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-before})
    if r.returncode:raise RuntimeError(r.stderr)
   validation=json.loads((checked/'check.json').read_text())
   if validation['source_sha256']!=record['sha256']:raise ValueError('camera source identity differs')
  for n,h in candidates.items():
   if sha(HERE/n)!=h:raise ValueError('camera candidate changed')
  for c,p in paths.items():
   if sha(p)!=source_identities[c]:raise ValueError('source admission identity changed')
  receipt={'status':'scientific camera component independently checked live','scene':args.scene,'component':component,'official_split':group['official_split'],'research_splits':group['research_splits'],'source_record_sha256':source_identities[component],'source_sha256':record['sha256'],'source_generation':record['source_metadata']['generation'],'admitted_source_record_hashes':source_identities,'transfer':transfer,'checks':checks,'validation':validation,'candidate_hashes':candidates,'runtime_lock':lock,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'combined_working_set_bytes':total(working),'artifacts':{str(p.relative_to(destination)):sha(p) for folder in (base,decoded) for p in folder.rglob('*') if p.is_file()},'scope':'native camera bytes/keys retained; image/mask decoding, task assembly, immutable publication/replay and scientific protocol remain open'}
  data=(json.dumps(receipt,indent=2)+'\n').encode()
  if total(working)+len(data)>limit:raise ValueError('combined camera working-set cap exceeded')
  receipt_path.write_bytes(data);print('verified scientific camera component',component,validation['rows'],flush=True)
if __name__=='__main__':main()
