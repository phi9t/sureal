"""Offline Insula archive producer and downloaded-byte verifier."""
import json,sys
from pathlib import Path
from resources.resource_archive import create_archive,verify_archive,sha
job=json.loads(Path('/tmp/inputs/job.json').read_text());mode=sys.argv[1]
if mode=='create':
 for name,digest in job['source_sha256'].items():assert sha(Path('/source')/name)==digest
 manifest=create_archive('/source',job['source_sha256'],'/outputs/archive.tar.gz',max_bytes=job['max_bytes'])
 Path('/outputs/manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2))
 check=verify_archive('/outputs/archive.tar.gz',manifest,max_bytes=job['max_bytes'])
elif mode in ('verify','rehydrate'):
 assert sha('/source/manifest.json')==job['manifest_sha256']
 manifest=json.loads(Path('/source/manifest.json').read_text())
 check=verify_archive('/source/archive.tar.gz',manifest,max_bytes=job['max_bytes'])
 if mode=='rehydrate':
  from resources.resource_rehydrate import rehydrate_archive
  check=rehydrate_archive('/source/archive.tar.gz',manifest,'/outputs/restored',max_bytes=job['max_bytes'])
else:raise ValueError('unknown archive operation')
Path('/outputs/check.json').write_text(json.dumps(check,indent=2));print('PASS offline archive',mode,flush=True)
