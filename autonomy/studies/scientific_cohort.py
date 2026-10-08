#!/usr/bin/env python3
"""Sequential verified scene lifecycle; no training or automatic protocol closure."""
import argparse,fcntl,json,resource,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from evidence.source_snapshot import file_sha256 as sha
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from dataset.scientific_admission import admit_scene
from dataset.cohort_resume import verify_registered_checkpoint
DRIVER=Path(__file__).resolve()
HERE=DRIVER.parents[1]
CACHE=Path.home()/'.cache/waystone/waymo-perception'
WORKING=CACHE/'scientific-processing'
POINT_COMPONENTS=['lidar_calibration','camera_calibration','vehicle_pose','lidar_pose','lidar_camera_projection','lidar_segmentation','lidar_box','reconstruction']
CAMERA_COMPONENTS=['camera_image','camera_segmentation','camera_box']
SCIENTIFIC_COHORT_TARGET='//autonomy/studies:scientific_cohort'
def save(p,data):
 p.write_text(json.dumps(data,indent=2)+'\n')
def total(p):return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
def audit(path,artifact_root=None):
 receipt=json.loads(path.read_text());root=artifact_root or path.parent
 if not receipt.get('checks') or any(c['exit_code'] for c in receipt['checks']):raise ValueError('successful live checks required: '+str(path))
 for n,h in receipt['candidate_hashes'].items():
  if sha(HERE/n)!=h:raise ValueError('current candidate differs: '+n)
 for n,h in receipt['artifacts'].items():
  if sha(root/n)!=h:raise ValueError('artifact differs: '+n)
 return receipt

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--scene',action='append',required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--initial-processing',type=Path);parser.add_argument('--trusted-checkpoints',type=Path);parser.add_argument('--expected-trusted-checkpoints-sha256');args=parser.parse_args()
 if len(set(args.scene))!=len(args.scene):raise ValueError('duplicate requested scene')
 base=args.output.resolve()
 if WORKING.resolve() not in base.parents:raise ValueError('queue must remain in accounted scientific working root')
 base.mkdir(parents=True,exist_ok=True);owner=(WORKING/'cohort-queue.lock').open('a')
 try:fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise ValueError('another cohort driver is live')
 manifest_path=HERE/'dataset/scientific-acquisition.candidate.json';manifest=json.loads(manifest_path.read_text());manifest['excluded_engineering_segments']=json.loads((HERE/'dataset/scientific-cohort.candidate.json').read_text())['excluded_engineering_segments']
 root=CACHE/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256']);driver_sha=sha(DRIVER);manifest_sha=sha(manifest_path)
 for index,scene in enumerate(args.scene):
  membership=manifest['scenes'][scene];paths={c:CACHE/'scientific-source-audit'/f"{membership['official_split']}-{c}-{scene}.json" for c in manifest['components']};records={c:json.loads(p.read_text()) for c,p in paths.items()};admit_scene(manifest,records,scene);source_hashes={c:sha(p) for c,p in paths.items()}
  scene_base=base/scene;checkpoint=scene_base/'receipt.json'
  if checkpoint.exists():
   verify_registered_checkpoint(checkpoint,scene=scene,registry=args.trusted_checkpoints,expected_registry_sha256=args.expected_trusted_checkpoints_sha256,code_root=HERE,expected_runtime_lock=lock,expected_manifest_sha256=manifest_sha,expected_source_hashes=source_hashes)
   print('verified completed queue scene',scene,flush=True);continue
  scene_base.mkdir(exist_ok=True);checks=[];retained={};started=datetime.now(timezone.utc).isoformat();tick=time.monotonic()
  def call(stage,cmd):
   t=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True,cwd=HERE);log=scene_base/(stage+'.log');log.write_text(r.stdout+r.stderr);checks.append({'stage':stage,'command':cmd,'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-t});print(stage,r.returncode,scene,flush=True)
   if r.returncode:raise RuntimeError(r.stderr[-2000:])
  def python(stage,name,*values):call(stage,['python3','-m','dataset.'+Path(name).stem,*map(str,values)])
  def remember(p):retained[str(p)]=sha(p)
  def bundle_cap(processing):
   files=[p for p in (processing/'sidecars').rglob('*') if p.is_file()];upper=sum(p.stat().st_size for p in files)+len(files)*1024+16*1024**2
   if total(WORKING)+upper>=15*1024**3:raise ValueError('aggregate component bundle working cap insufficient')
  def evict(stage,module,function,processing,publication,replay,ph,rh=None):
   code='import json; from '+module+' import '+function+'; r='+function+"('/outputs','/opt'"+(",'/srv'" if replay else '')+',expected_publication_sha256='+repr(ph)+(',expected_replay_sha256='+repr(rh) if replay else '')+"); print(json.dumps({'status':r['status'],'bytes_evicted':r['bytes_evicted']}))"
   plan=launch_plan(root,HERE,HERE,processing,['python','-c',code]);i=plan.index('--');mounts=['--bind',str(publication),'/opt']
   if replay:mounts+=['--ro-bind',str(replay),'/srv']
   plan[i:i]=mounts;call(stage,plan)
   name={'point-evict':'point-eviction.json','sidecar-evict':'sidecar-eviction.json','camera-evict':'camera-eviction.json'}[stage];p=processing/name;ev=json.loads(p.read_text())
   if not ev['status'].endswith('completed'):raise ValueError('incomplete eviction')
   for f in ev['files']:
    value=f['path'];target=processing/Path(value).relative_to('/outputs') if value.startswith('/outputs/') else publication/Path(value).relative_to('/opt')
    if target.exists():raise ValueError('evicted payload remains')
   if sha(publication/'receipt.json')!=ph or (replay and sha(replay/'receipt.json')!=rh):raise ValueError('eviction changed trusted receipts')
   remember(p)
  processing=args.initial_processing.resolve() if index==0 and args.initial_processing else scene_base/'points'
  python('point-preprocess','scientific-preprocess.py','--scene',scene,'--output',processing,'--reconstruct')
  for c in POINT_COMPONENTS:
   p=processing/'evidence'/c/'receipt.json';audit(p,processing);remember(p)
  reconstruction_sha=sha(processing/'evidence/reconstruction/receipt.json');publication=scene_base/'point-publication';python('point-publication','publish-scientific-scene.py',processing,publication,'--expected-receipt-sha256',reconstruction_sha);pub=audit(publication/'receipt.json');ph=sha(publication/'receipt.json');remember(publication/'receipt.json');replay=scene_base/'point-replay';usage=membership['research_splits'][0]
  python('point-replay','verify-scientific-replay.py',processing,publication,replay,'--expected-receipt-sha256',ph,'--usage',usage);point_replay=audit(replay/'receipt.json');rh=sha(replay/'receipt.json');remember(replay/'receipt.json')
  if point_replay['publication_receipt_sha256']!=ph or len(point_replay['checks'])!=2:raise ValueError('point replay linkage differs')
  evict('point-evict','dataset.verified_eviction','evict_points',processing,publication,replay,ph,rh)
  bundle_cap(processing);side_pub=scene_base/'sidecar-publication';python('sidecar-publication','publish-scientific-sidecars.py',processing,side_pub,'--expected-scene-receipt-sha256',reconstruction_sha);audit(side_pub/'receipt.json');sh=sha(side_pub/'receipt.json');remember(side_pub/'receipt.json');evict('sidecar-evict','dataset.sidecar_eviction','evict_sidecars',processing,side_pub,None,sh)
  camera=scene_base/'camera';call('camera-preprocess',['python3','-m','camera.scientific-camera-preprocess','--scene',scene,'--output',str(camera)]);camera_hashes={}
  for c in CAMERA_COMPONENTS:
   p=camera/'evidence'/c/'receipt.json';audit(p,camera);remember(p);camera_hashes[c]=sha(p)
  evidence=scene_base/'camera-evidence.json';save(evidence,{'scene':scene,'processing':str(camera),'receipt_hashes':camera_hashes});remember(evidence);camera_pub=scene_base/'camera-publication';call('camera-publication',['python3','-m','camera.publish-scientific-camera','--evidence',str(evidence),'--expected-evidence-sha256',sha(evidence),'--output',str(camera_pub)]);audit(camera_pub/'receipt.json');ch=sha(camera_pub/'receipt.json');remember(camera_pub/'receipt.json');camera_replay=scene_base/'camera-replay';call('camera-replay',['python3','-m','camera.verify-camera-replay',str(camera),str(camera_pub),str(camera_replay),'--expected-receipt-sha256',ch,'--usage',usage]);camera_result=audit(camera_replay/'receipt.json');crh=sha(camera_replay/'receipt.json');remember(camera_replay/'receipt.json')
  if camera_result['publication_receipt_sha256']!=ch or len(camera_result['checks'])!=2:raise ValueError('camera replay linkage differs')
  evict('camera-evict','camera.camera_eviction','evict_camera',camera,camera_pub,camera_replay,ch,crh)
  for c,p in paths.items():
   if sha(p)!=source_hashes[c]:raise ValueError('source admission changed during lifecycle')
  if sha(DRIVER)!=driver_sha or sha(manifest_path)!=manifest_sha or total(WORKING)>15*1024**3:raise ValueError('driver/cohort/cap changed')
  for p in scene_base.glob('*.log'):remember(p)
  save(checkpoint,{'status':'native scientific scene point/camera lifecycle independently verified; protocol remains open','scene':scene,'membership':membership,'checks':checks,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'driver_sha256':driver_sha,'manifest_sha256':manifest_sha,'source_record_hashes':source_hashes,'runtime_lock':lock,'retained_evidence_hashes':retained,'point_validation':point_replay['validation'],'camera_validation':camera_result['validation'],'point_hdfs_uri':pub['archive_hdfs_uri'],'camera_hdfs_uri':json.loads((camera_pub/'receipt.json').read_text())['archive_hdfs_uri'],'scope':'native preprocessing only; independent full queue audit, class maps, full task/cohort/scientific protocol/model comparisons remain open'})
  print('PASS complete queued native scene',scene,flush=True)
if __name__=='__main__':main()
