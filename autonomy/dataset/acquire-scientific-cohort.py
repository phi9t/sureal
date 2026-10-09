#!/usr/bin/env python3
"""Resumable generation-pinned scientific sources, HDFS mirror and live inventory."""
from datetime import datetime,timezone
import base64,hashlib,json
from pathlib import Path
import subprocess,tempfile
from dataset.blob_storage import default_blob_store, default_store_descriptor, put_blob, source_blob_key
from dataset.launches import build_dataset_plan, load_dataset_runtime, plan_receipt, run_dataset_plan
from evidence.source_snapshot import file_sha256
from insula.staging_lease import staging_lease

HERE=Path(__file__).resolve().parents[1]
CACHE=Path.home()/'.cache/waystone/waymo-perception'
RECORDS=CACHE/'scientific-source-audit'

def call(args):
    r=subprocess.run(args,capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stderr[-2000:])
    return r.stdout

def hashes(path):
    sha=hashlib.sha256();md5=hashlib.md5()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):sha.update(data);md5.update(data)
    return sha.hexdigest(),base64.b64encode(md5.digest()).decode()

def main():
    manifest=json.loads((HERE/'dataset/scientific-acquisition.candidate.json').read_text());RECORDS.mkdir(exist_ok=True)
    retained=sum(o['size_bytes'] for o in json.loads((HERE/'dataset/dataset.lock.json').read_text())['objects'])
    maximum=min(manifest['per_object_limit_bytes'],manifest['local_staging_limit_bytes']-retained)
    if maximum<=0:raise ValueError('no bounded raw staging capacity')
    runtime=load_dataset_runtime(CACHE);lock=runtime.data
    blob_store=default_blob_store();store_descriptor=default_store_descriptor()
    for scene,group in manifest['scenes'].items():
        official=group['official_split']
        for component in manifest['components']:
            record=RECORDS/f'{official}-{component}-{scene}.json'
            if record.exists():continue
            started=datetime.now(timezone.utc).isoformat()
            uri=f'gs://waymo_open_dataset_v_2_0_1/{official}/{component}/{scene}.parquet'
            metadata=json.loads(call([str(HERE/'dataset/gcs.sh'),'--','storage','objects','describe',uri,'--format=json']))
            if int(metadata['size'])>maximum:raise ValueError(f'{component}/{scene} exceeds remaining {maximum}-byte raw capacity; no scene dropped')
            with tempfile.TemporaryDirectory(dir=RECORDS,prefix='stage-') as tmp:
                stage=Path(tmp);inputs=stage/'input';inputs.mkdir();out=stage/'outputs';out.mkdir();payload=inputs/'source.parquet'
                call([str(HERE/'dataset/gcs.sh'),'--','storage','cp',metadata['storage_url'],str(payload)])
                sha,md5=hashes(payload)
                if payload.stat().st_size!=int(metadata['size']) or md5!=metadata['md5_hash']:raise ValueError('source integrity')
                blob=put_blob(blob_store,source_blob_key(official,component,scene),payload)
                payload.unlink()
                blob_store.get(blob['key'],payload,blob['sha256'],expected_bytes=blob['bytes'])
                if payload.stat().st_size!=int(metadata['size']) or hashes(payload)[0]!=sha:raise ValueError('blob download-back integrity; stored source changed')
                plan=build_dataset_plan(runtime,code_root=HERE,source=inputs,output=out,command=['python','-m','dataset.shard_inventory','/source/source.parquet',scene,'/outputs/inventory.json'])
                live=run_dataset_plan(plan,capture_output=True,text=True)
                if live.returncode:raise RuntimeError(live.stderr[-2000:])
                result={'scene':scene,'component':component,'official_split':official,'research_splits':group['research_splits'],'source_metadata':metadata,'sha256':sha,'blob':blob,'store_descriptor':store_descriptor,'inventory':json.loads((out/'inventory.json').read_text()),'live_log':live.stdout,'runtime_lock':lock,'launch_plan':plan_receipt(plan),'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'inventory_code_sha256':file_sha256(HERE/'dataset/shard_inventory.py'),'raw_peak_bytes_including_retained_engineering':retained+int(metadata['size'])}
                record.write_text(json.dumps(result,indent=2)+'\n')
            print('verified',official,component,scene,result['inventory']['rows'],flush=True)

if __name__=='__main__':
    with staging_lease(CACHE/'raw-staging.lock'):
        main()
