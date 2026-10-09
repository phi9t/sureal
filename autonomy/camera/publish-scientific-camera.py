#!/usr/bin/env python3
"""Publish externally audited native camera sidecars through immutable blobs."""
import argparse,json,resource,time
from datetime import datetime,timezone
from pathlib import Path
from camera.blob_publication import camera_blob_key, publication_blob_store
from dataset.blob_storage import blob_transfer_check
from insula.launch_plan import build_plan, load_default_runtime_lock, record_plan, run_plan
from insula.runtime_roots import current_cpu_rootfs
from evidence.source_snapshot import file_sha256 as sha
HERE=Path(__file__).resolve().parents[1]
COMPONENTS=['camera_image','camera_segmentation','camera_box']
def total(p):return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True);parser.add_argument('--expected-evidence-sha256',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 if sha(args.evidence)!=args.expected_evidence_sha256:raise ValueError('trusted camera evidence differs')
 evidence=json.loads(args.evidence.read_text());processing=Path(evidence['processing']);scene=evidence['scene'];expected={};sources={};membership=None
 for component in COMPONENTS:
  p=processing/'evidence'/component/'receipt.json'
  if sha(p)!=evidence['receipt_hashes'][component]:raise ValueError('trusted component receipt differs')
  r=json.loads(p.read_text());partition=(r['official_split'],r['research_splits'])
  if r['scene']!=scene or r['component']!=component or [c['stage'] for c in r['checks']]!=['decode','independent-check'] or any(c['exit_code'] for c in r['checks']):raise ValueError('native camera receipt/check differs')
  if membership is not None and membership!=partition:raise ValueError('camera partition differs')
  membership=partition
  for n,h in r['candidate_hashes'].items():
   if sha(HERE/n)!=h:raise ValueError('camera processing candidate changed')
  for n,h in r['artifacts'].items():
   if sha(processing/n)!=h:raise ValueError('camera source artifact changed')
   if n.startswith('sidecars/'+component+'/'):expected[n[len('sidecars/'):]]=h
  sources[component]={'sha256':r['source_sha256'],'generation':r['source_generation'],'source_record_sha256':r['source_record_sha256']}
 cache=Path.home()/'.cache/waystone/waymo-perception';working=cache/'scientific-processing';base=args.output.resolve()
 if working.resolve() not in base.parents or working.resolve() not in processing.resolve().parents:raise ValueError('camera paths must remain accounted scientific outputs')
 runtime=load_default_runtime_lock(current_cpu_rootfs(cache));lock=runtime.data;base.mkdir(parents=True,exist_ok=False);inputs=base/'input';packed=base/'packed';checked=base/'checked'
 for p in (inputs,packed,checked):p.mkdir()
 provenance={'scene':scene,'official_split':membership[0],'research_splits':membership[1],'camera_evidence_sha256':args.expected_evidence_sha256,'source_receipt_hashes':evidence['receipt_hashes'],'sources':sources}
 store,store_descriptor=publication_blob_store()
 (inputs/'trusted.json').write_text(json.dumps({'files':expected,'provenance':provenance},indent=2)+'\n');names=['camera/publish-scientific-camera.py','camera/blob_publication.py','blob_store/core.py','dataset/component_archive.py','dataset/component_archive_validate.py','insula/launch_plan.py','insula/runtime_roots.py'];candidates={n:sha(HERE/n) for n in names};checks=[];started=datetime.now(timezone.utc).isoformat();tick=time.monotonic()
 def call(stage,plan):
  t=time.monotonic();r=run_plan(plan,capture_output=True,text=True);(base/(stage+'.log')).write_text(r.stdout+r.stderr);checks.append({'stage':stage,'launch_plan':record_plan(plan),'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-t})
  if r.returncode:raise RuntimeError(r.stderr)
  print('PASS',stage,flush=True)
 other=total(working)-total(processing/'sidecars')
 code="import json; from pathlib import Path; from dataset.component_archive import create_component_archive; d=json.loads(Path('/mnt/trusted.json').read_text()); r=create_component_archive('/source/sidecars','/outputs/camera.tar',expected_files=d['files'],provenance=d['provenance'],other_bytes="+str(other)+",budget_bytes=15*1024**3); Path('/outputs/archive.json').write_text(json.dumps(r)); print('PASS camera bundle',r['files'])"
 plan=build_plan(runtime,code=HERE,source=processing,output=packed,command=['python','-c',code],named_inputs={'/mnt':inputs});call('pack-live',plan)
 meta=json.loads((packed/'archive.json').read_text());archive=packed/'camera.tar';archive_key=camera_blob_key(scene,'archive','camera.tar');readback=packed/'camera-readback.tar';archive_blob=dict(store.put(archive_key,archive),verified_by_readback=True);checks.append(blob_transfer_check('archive-blob-put',archive_blob));archive.unlink();store.get(archive_blob['key'],readback,archive_blob['sha256'],expected_bytes=archive_blob['bytes']);checks.append(blob_transfer_check('archive-blob-download',archive_blob));readback.replace(archive)
 if sha(archive)!=meta['sha256']:raise ValueError('camera mirror differs')
 code="import json; from pathlib import Path; from dataset.component_archive_validate import validate_component_archive; r=validate_component_archive('/source/camera.tar',expected_archive_sha256="+repr(meta['sha256'])+",expected_manifest_sha256="+repr(meta['manifest_sha256'])+"); Path('/outputs/bundle-check.json').write_text(json.dumps(r)); print('PASS camera bundle independent',r['files'])"
 call('independent-bundle-live',build_plan(runtime,code=HERE,source=packed,output=checked,command=['python','-c',code]));validation=json.loads((checked/'bundle-check.json').read_text())
 if validation['provenance']!=provenance or validation['files']!=len(expected):raise ValueError('camera lineage differs')
 publication={'schema_version':1,'role':'scientific-native-camera-components','scene':scene,'official_split':membership[0],'research_splits':membership[1],'store_descriptor':store_descriptor,'archive_blob':archive_blob,'archive':meta,'provenance':provenance};p=packed/'publication.json';p.write_text(json.dumps(publication,indent=2)+'\n');manifest_sha=sha(p);manifest_key=camera_blob_key(scene,'manifest','publication.json');manifest_blob=dict(store.put(manifest_key,p),verified_by_readback=True);checks.append(blob_transfer_check('manifest-blob-put-last',manifest_blob));store.get(manifest_blob['key'],checked/'publication.json',manifest_blob['sha256'],expected_bytes=manifest_blob['bytes']);checks.append(blob_transfer_check('manifest-blob-download',manifest_blob))
 if sha(checked/'publication.json')!=manifest_sha:raise ValueError('camera manifest mirror differs')
 for n,h in candidates.items():
  if sha(HERE/n)!=h:raise ValueError('camera publication candidate changed')
 if sha(args.evidence)!=args.expected_evidence_sha256 or total(working)>15*1024**3:raise ValueError('camera evidence or final working cap differs')
 receipt={'status':'scientific native camera bundle independently mirrored live','scene':scene,'checks':checks,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'runtime_lock':lock,'candidate_hashes':candidates,'camera_evidence_sha256':args.expected_evidence_sha256,'component_receipt_hashes':evidence['receipt_hashes'],'store_descriptor':store_descriptor,'archive':meta,'archive_blob':archive_blob,'publication_manifest_blob':manifest_blob,'publication_manifest_sha256':manifest_sha,'validation':validation,'combined_working_set_bytes':total(working),'artifacts':{str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()},'scope':'native camera binary/scalar/key bundle; replay, verified eviction, image/mask decoding and scientific task/protocol readiness remain open'};(base/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS immutable camera publication',scene,flush=True)
if __name__=='__main__':main()
