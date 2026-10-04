#!/usr/bin/env python3
"""Resumable generation-pinned scientific sources, HDFS mirror and live inventory."""
from datetime import datetime,timezone
import base64,hashlib,json
from pathlib import Path
import subprocess,tempfile
from pipeline.staging_lease import staging_lease

HERE=Path(__file__).resolve().parent
CACHE=Path.home()/'.cache/waystone/waymo-perception'
RECORDS=CACHE/'scientific-source-audit'
WAYSTONE='/data02/home/philip.yang/workspace/waystone/scripts/waystone'

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
    manifest=json.loads((HERE/'scientific-acquisition.candidate.json').read_text());RECORDS.mkdir(exist_ok=True)
    retained=sum(o['size_bytes'] for o in json.loads((HERE/'dataset.lock.json').read_text())['objects'])
    maximum=min(manifest['per_object_limit_bytes'],manifest['local_staging_limit_bytes']-retained)
    if maximum<=0:raise ValueError('no bounded raw staging capacity')
    for scene,group in manifest['scenes'].items():
        official=group['official_split']
        for component in manifest['components']:
            record=RECORDS/f'{official}-{component}-{scene}.json'
            if record.exists():continue
            started=datetime.now(timezone.utc).isoformat()
            uri=f'gs://waymo_open_dataset_v_2_0_1/{official}/{component}/{scene}.parquet'
            metadata=json.loads(call([str(HERE/'gcs.sh'),'--','storage','objects','describe',uri,'--format=json']))
            if int(metadata['size'])>maximum:raise ValueError(f'{component}/{scene} exceeds remaining {maximum}-byte raw capacity; no scene dropped')
            with tempfile.TemporaryDirectory(dir=RECORDS,prefix='stage-') as tmp:
                stage=Path(tmp);inputs=stage/'input';inputs.mkdir();out=stage/'outputs';out.mkdir();payload=inputs/'source.parquet'
                call([str(HERE/'gcs.sh'),'--','storage','cp',metadata['storage_url'],str(payload)])
                sha,md5=hashes(payload)
                if payload.stat().st_size!=int(metadata['size']) or md5!=metadata['md5_hash']:raise ValueError('source integrity')
                target=manifest['hdfs_root']+f'/{official}/{component}/{scene}.parquet'
                transfer=subprocess.run([WAYSTONE,'put','--mkdir-parents',str(payload),target],capture_output=True,text=True)
                # Existing identical mirrors are accepted only after download-back
                # verification. Conflicting content is never overwritten.
                payload.unlink()
                try:call([WAYSTONE,'get',target,str(payload)])
                except RuntimeError as error:raise RuntimeError(transfer.stderr[-1000:]+'\n'+str(error))
                if payload.stat().st_size!=int(metadata['size']) or hashes(payload)[0]!=sha:raise ValueError('HDFS download-back integrity; mirror not overwritten')
                log=call([str(HERE/'enter.sh'),'--source',str(inputs),'--output',str(out),'--offline','--','python','-m','pipeline.shard_inventory','/source/source.parquet',scene,'/outputs/inventory.json'])
                result={'scene':scene,'component':component,'official_split':official,'research_splits':group['research_splits'],'source_metadata':metadata,'sha256':sha,'hdfs_uri':target,'hdfs_roundtrip_sha256':sha,'inventory':json.loads((out/'inventory.json').read_text()),'live_log':log,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'inventory_code_sha256':hashlib.sha256((HERE/'pipeline/shard_inventory.py').read_bytes()).hexdigest(),'raw_peak_bytes_including_retained_engineering':retained+int(metadata['size'])}
                record.write_text(json.dumps(result,indent=2)+'\n')
            print('verified',official,component,scene,result['inventory']['rows'],flush=True)

if __name__=='__main__':
    with staging_lease(CACHE/'raw-staging.lock'):
        main()
