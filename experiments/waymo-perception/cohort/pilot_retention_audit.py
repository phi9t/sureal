"""Independent whole-pilot membership/readback/live-recovery admission."""
import copy,hashlib,json,resource,time
from pathlib import Path,PurePosixPath
start=time.monotonic()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
base=Path('/tmp/inputs')
pub=json.loads((base/'publication.json').read_text());original=json.loads((base/'readback.json').read_text());expected=json.loads((base/'expected.json').read_text())
assert sha(base/'readback.json')==pub['publication_manifest_sha256']
assert sha(base/'expected.json')==pub['pilot_inventory_sha256']

def validate(candidate,check_local=True):
 if candidate.get('manifest_readback_exact') is not True or candidate.get('source_admission_complete') is not True:raise ValueError('readback/source admission required')
 for key in ['chunks','source_sha256','parent_receipts','pilot_inventory_sha256','runtime_lock','source_pins','waystone_tool_sha256','host_source_pins']:
  if candidate[key]!=original[key]:raise ValueError('global manifest differs')
 if candidate['source_sha256']!=expected['source_sha256'] or candidate['parent_receipts']!=expected['parent_receipts']:raise ValueError('independent parent inventory differs')
 uri=candidate['publication_manifest_hdfs_uri'];prefix=uri.rsplit('/',1)[0]
 if not prefix.startswith('hdfs://harunava/user/tiger/waystone/sureal/runs/perception-sustained-pilot/balanced16-sustained-admission-') or uri!=prefix+'/publication-manifest.json':raise ValueError('wrong pilot namespace')
 union={};payload=0
 for chunk in candidate['chunks']:
  manifest=chunk['manifest'];members=manifest['members'];size=sum(member['bytes'] for member in members);digest=manifest['archive_sha256']
  if size!=manifest['payload_bytes'] or size>768*1024**2 or chunk['archive_hdfs_uri']!=prefix+'/'+digest+'/archive.tar.gz' or chunk['manifest_hdfs_uri']!=prefix+'/'+digest+'/manifest.json':raise ValueError('chunk identity/size differs')
  checks=chunk['checks']
  if [check['stage'] for check in checks]!=['create-live','archive-put','archive-get','manifest-put','manifest-get','verify-live','rehydrate-live'] or any(check['exit_code']!=0 for check in checks):raise ValueError('missing live or transfer gate')
  for index in (0,5,6):
   value=checks[index]['validation']
   if value['archive_sha256']!=digest or not value['exact_members_and_hashes'] or value['members']!=len(members) or value['payload_bytes']!=size:raise ValueError('live recovery member proof differs')
   if index==6 and not value['verified_rehydration']:raise ValueError('missing rehydration')
  for member in members:
   name=member['path'];path=PurePosixPath(name)
   if path.is_absolute() or '..' in path.parts or str(path)!=name or name in union or name not in expected['source_sha256']:raise ValueError('foreign or duplicate pilot member')
   local=Path('/source')/name
   if check_local and (local.is_symlink() or not local.is_file() or local.stat().st_size!=member['bytes'] or sha(local)!=member['sha256']):raise ValueError('original pilot bytes differ')
   union[name]=member['sha256']
  payload+=size
 if union!=expected['source_sha256']:raise ValueError('incomplete pilot recovery')
 return {'files':len(union),'chunks':len(candidate['chunks']),'payload_bytes':payload,'whole_member_union_exact':True,'all_chunks_live_rehydrated':True}

result=validate(pub);refused=0
for fault in ['readback','missing_chunk','member_hash','namespace','missing_rehydrate']:
 bad=copy.deepcopy(pub)
 if fault=='readback':bad['manifest_readback_exact']=False
 elif fault=='missing_chunk':bad['chunks'].pop()
 elif fault=='member_hash':bad['chunks'][0]['manifest']['members'][0]['sha256']='0'*64
 elif fault=='namespace':bad['publication_manifest_hdfs_uri']='hdfs://foreign/unknown/publication-manifest.json'
 else:bad['chunks'][0]['checks'].pop()
 try:validate(bad,False)
 except ValueError:refused+=1
 else:raise AssertionError('corrupt cache retention admitted')
assert refused==5
result.update({'corrupt_retention_copies_refused':refused,'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'all original native-pilot bytes, global HDFS readback and live recovery admission; no historical model release or scientific acceptance'})
Path('/outputs/check.json').write_text(json.dumps(result,indent=2));print('PASS independent native-pilot retention admission',result)
