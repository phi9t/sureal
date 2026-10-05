"""Scan admitted training metadata and freeze a balanced fixture selection."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PACKAGE))
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from dataset.staged_source import staged_source
from pipeline.training_box_replay import retained_raw_bytes
from balanced import select_balanced,coverage_summary
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--transport',choices=['hdfs','gcs'],default='hdfs');args=parser.parse_args()
cache=Path.home()/'.cache/waystone/waymo-perception';root=cache/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256']);protocol=json.loads((PACKAGE/'research/pointpillars-scientific-protocol.candidate.json').read_text());destination=cache/('scientific-processing/balanced-coverage-scan-'+args.transport+'-v2');destination.mkdir();frames=[];receipts=[];pins={str(p):sha(p) for p in [PACKAGE/'cohort/scan_boxes.py',PACKAGE/'cohort/balanced.py',PACKAGE/'cohort/gcs_metadata_get.py']};retained=retained_raw_bytes(cache,PACKAGE)
for i,scene in enumerate(sorted(protocol['cohorts']['train'])):
 srcpath=cache/'scientific-source-audit'/f'training-lidar_box-{scene}.json';record=json.loads(srcpath.read_text());assert record['scene']==scene and record['official_split']=='training' and record['research_splits']==['train'];base=destination/scene;base.mkdir();inputs=base/'input';inputs.mkdir();(inputs/'source.json').write_bytes(srcpath.read_bytes());out=base/'output';out.mkdir()
 with staged_source(record,cache,retained_bytes=retained,limit_bytes=2*1024**3,transfer_command=['timeout','--kill-after=5s','120s',sys.executable,str(PACKAGE/'cohort/gcs_metadata_get.py')] if args.transport=='gcs' else ['timeout','--kill-after=5s','120s','/data02/home/philip.yang/workspace/waystone/scripts/waystone']) as (raw,transfer):
  command=launch_plan(root,PACKAGE,raw.parent,out,['python','/experiment/cohort/scan_boxes.py']);j=command.index('--');command[j:j]=['--ro-bind',str(inputs),'/tmp/input'];run=subprocess.run(command,capture_output=True,text=True,timeout=120);(out/'live.log').write_text(run.stdout+run.stderr);assert run.returncode==0,(scene,run.stderr);result=json.loads((out/'frames.json').read_text());frames.extend(result['frames']);receipt={'checks':[{'command':command,'exit_code':0}],'source_receipt_sha256':sha(srcpath),'transfer':transfer,'artifacts':{str(p):sha(p) for p in out.iterdir()},'runtime_lock':lock,'worker_sha256':pins[str(PACKAGE/'cohort/scan_boxes.py')]};(base/'receipt.json').write_text(json.dumps(receipt,indent=2));receipts.append({'scene':scene,'receipt':str(base/'receipt.json'),'sha256':sha(base/'receipt.json')})
 assert all(sha(p)==h for p,h in pins.items());print('SCANNED',i+1,'/64',scene,flush=True)
 (PACKAGE/'research/balanced-coverage-scan-progress.json').write_text(json.dumps({'scanned_scenes':i+1,'expected_scenes':64,'frame_count':len(frames),'coverage':coverage_summary(frames)},indent=2)+'\n')
selected=select_balanced(frames);candidate={'selection':'balanced-v1 training-label coverage, inverse available unique-track weighted greedy novelty; SHA256 identity tie break; no model outcomes','requirements':{'frames':16,'per_class':{'eligible_objects':16,'unique_tracks':8,'frames':8,'scenes':4}},'frames':selected,'coverage':coverage_summary(selected),'available_coverage':coverage_summary(frames),'sources':receipts,'worker_hashes':pins,'metadata_transport':args.transport,'scope':'metadata selection only; physical packing/anchor coverage admission required'}
(PACKAGE/'research/balanced16-selection.candidate.json').write_text(json.dumps(candidate,indent=2)+'\n');print('SELECTED',json.dumps(candidate['coverage']),flush=True)
