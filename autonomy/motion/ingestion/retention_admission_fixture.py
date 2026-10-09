import pathlib,json,copy,time,resource
from blob_store.core import legacy_project_uri_to_key
from evidence.source_snapshot import file_sha256 as sha
start=time.monotonic();base=pathlib.Path('/source')
PREFIX='runs/perception-motion/'
def blob_key(value):
 try:key=legacy_project_uri_to_key(value)
 except ValueError as error:raise ValueError('namespace') from error
 if not key.startswith(PREFIX):raise ValueError('namespace')
 return key
def validate(pub,original,expected,check_local=True):
 if not pub['manifest_readback_exact'] or pub['chunk_limit_bytes']!=32*1024**2:raise ValueError('readback/chunk admission')
 for key in ['chunks','source_sha256','parent_receipts','runtime_lock','source_pins','tool_pins','hdfs_prefix']:
  if pub[key]!=original[key]:raise ValueError('global readback differs')
 prefix=pub['hdfs_prefix'];prefix_key=blob_key(prefix)
 if blob_key(pub['publication_manifest_hdfs_uri'])!=prefix_key+'/publication-manifest.json':raise ValueError('namespace')
 if pub['source_sha256']!=expected:raise ValueError('parent artifact set')
 union={};payload=0
 for i,chunk in enumerate(pub['chunks']):
  manifest=chunk['manifest'];members=manifest['members'];size=sum(x['bytes'] for x in members);digest=manifest['archive_sha256'];uri=prefix_key+'/chunk-'+str(i).zfill(3)+'/'+digest
  if chunk['index']!=i or blob_key(chunk['archive_hdfs_uri'])!=uri+'/archive.tar.gz' or blob_key(chunk['manifest_hdfs_uri'])!=uri+'/manifest.json' or size!=manifest['payload_bytes'] or size>pub['chunk_limit_bytes']:raise ValueError('chunk identity/size')
  if [x['mode'] for x in chunk['live_proofs']]!=['create','verify','rehydrate']:raise ValueError('missing live proof')
  for proof in chunk['live_proofs']:
   v=proof['validation']
   if proof['exit_code']!=0 or not v['exact_members_and_hashes'] or v['archive_sha256']!=digest or v['members']!=len(members) or v['payload_bytes']!=size:raise ValueError('live member proof')
   if proof['mode']=='rehydrate' and not v['verified_rehydration']:raise ValueError('recovery proof')
  for member in members:
   name=member['path'];path=pathlib.PurePosixPath(name)
   if path.is_absolute() or '..' in path.parts or str(path)!=name or name in union or path.parts[0] not in ['motion-delta-components-v1','motion-current-geometry-v1']:raise ValueError('unsafe/duplicate member')
   if check_local and ((base/name).stat().st_size!=member['bytes'] or sha(base/name)!=member['sha256']):raise ValueError('local original differs')
   union[name]=member['sha256']
  payload+=size
 if union!=expected:raise ValueError('incomplete recovery')
 return {'files':len(union),'chunks':len(pub['chunks']),'payload_bytes':payload,'whole_member_union_exact':True,'all_chunks_live_rehydrated':True}
pub=json.loads(pathlib.Path('/experiment/publication.json').read_text());readback=pathlib.Path('/experiment/readback.json');original=json.loads(readback.read_text());expected=json.loads(pathlib.Path('/experiment/expected.json').read_text());assert sha(readback)==pub['publication_manifest_sha256'];result=validate(pub,original,expected);refused=0
for fault in ['readback','missing_chunk','member_hash','namespace','missing_rehydrate']:
 bad=copy.deepcopy(pub)
 if fault=='readback':bad['manifest_readback_exact']=False
 elif fault=='missing_chunk':bad['chunks'].pop()
 elif fault=='member_hash':bad['chunks'][0]['manifest']['members'][0]['sha256']='0'*64
 elif fault=='namespace':bad['hdfs_prefix']='hdfs://foreign/unknown'
 else:bad['chunks'][0]['live_proofs'].pop()
 try:validate(bad,original,expected,False)
 except ValueError:refused+=1
 else:raise AssertionError('bad retention admitted')
assert refused==5;result.update({'corrupt_retention_copies_refused':refused,'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'current local member union, global HDFS readback and retained live chunk recovery admission; no local deletion performed by verifier'});pathlib.Path('/outputs/check.json').write_text(json.dumps(result,indent=2));print('PASS independent live Motion HDFS retention admission',result)
