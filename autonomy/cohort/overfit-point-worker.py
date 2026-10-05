import sys,json,hashlib,io,tarfile,time,resource,importlib.util
from pathlib import Path
import numpy as np
sys.path.insert(0,'/tmp/workers')
from dataset.scientific_dataset import iter_scene_records
from dataset.scene_archive_validate import validate_archive
assert importlib.util.find_spec('tensorflow') is None
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
job=json.loads(Path('/tmp/input/job.json').read_text());scene=job['scene'];timestamps=job['timestamps'];archive=Path('/source/scene.tar');pub=Path('/tmp/input/publication.json');publication=json.loads(pub.read_text());assert sha(pub)==job['publication_sha256'];started=time.monotonic();mode=sys.argv[1];summaries=[]
assert publication['scene']==scene and publication['role']=='scientific' and publication['official_split']=='training' and publication['research_splits']==['train']
if mode=='producer':
 from overfit_points import assemble_frame
 selected={t:[] for t in timestamps};records=0;points=0
 for record in iter_scene_records(archive,pub,expected_publication_sha256=job['publication_sha256'],usage='train'):
  records+=1
  if record['return_present']:points+=len(record['observations']['xyz'])
  if record['identity']['timestamp'] in selected:selected[record['identity']['timestamp']].append(record)
 for timestamp in sorted(selected):
  arrays=assemble_frame(selected[timestamp],scene=scene,timestamp=timestamp);path=Path('/outputs')/f'{timestamp}.npz';np.savez(path,**arrays);assert path.stat().st_size<=64*1024**2
  summaries.append({'timestamp_micros':timestamp,'points':len(arrays['physical_points']),'file':path.name,'sha256':sha(path),'bytes':path.stat().st_size})
elif mode=='reference':
 assert sha('/tmp/produced/report.json')==job['producer_report_sha256'];produced=json.loads(Path('/tmp/produced/report.json').read_text());assert len(produced['frames'])==len(timestamps)
 validation=validate_archive(archive,expected_report_sha256=publication['archive']['report_sha256'],expected_archive_sha256=publication['archive']['sha256']);parts={t:{} for t in timestamps}
 with tarfile.open(archive,'r|') as tar:
  first=tar.next();report=json.loads(tar.extractfile(first).read());records=len(report['rows']);points=report['points']
  for row in sorted(report['rows'],key=lambda r:f"{r['context']}-{r['timestamp']}-{r['laser']}-{r['return']}.npz"):
   assert row['context']==scene;key=(row['laser'],row['return']);t=row['timestamp']
   if row['return_present']:
    member=tar.next();assert member.name==row['artifact']
    if t not in parts:continue
    data=tar.extractfile(member).read();assert hashlib.sha256(data).hexdigest()==row['sha256']
    with np.load(io.BytesIO(data),allow_pickle=False) as raw:
     xyz=raw['xyz'];physical=raw['physical_features'];pixels=raw['pixels'];nlz=raw['nlz'];n=row['points'];assert xyz.shape==(n,3) and physical.shape==(n,3) and pixels.shape==(n,2) and nlz.shape==(n,)
     values=np.empty((n,4),dtype=np.float64);values[:,:3]=xyz;values[:,3]=physical[:,1]
     identity=np.empty((n,4),dtype=np.int64);identity[:,0]=key[0];identity[:,1]=key[1];identity[:,2:]=pixels
     payload=(values,identity,nlz.astype(np.int64),[key[0],key[1],1,n])
   elif t in parts:payload=(np.empty((0,4)),np.empty((0,4),dtype=np.int64),np.empty((0,),dtype=np.int64),[key[0],key[1],0,0])
   if t in parts:assert key not in parts[t];parts[t][key]=payload
  assert tar.next() is None
 for timestamp in sorted(parts):
  frame=parts[timestamp];assert set(frame)=={(l,r) for l in range(1,6) for r in (1,2)};ordered=[frame[k] for k in sorted(frame)];expected={'physical_points':np.concatenate([v[0] for v in ordered]),'measurement_identity':np.concatenate([v[1] for v in ordered]),'evaluation_nlz':np.concatenate([v[2] for v in ordered]),'return_states':np.asarray([v[3] for v in ordered],dtype=np.int64)}
  entries=[x for x in produced['frames'] if x['timestamp_micros']==timestamp];assert len(entries)==1;entry=entries[0];path=Path('/tmp/produced')/entry['file'];assert sha(path)==entry['sha256'] and path.stat().st_size==entry['bytes']
  with np.load(path,allow_pickle=False) as arrays:
   assert set(arrays.files)==set(expected)
   for name,value in expected.items():np.testing.assert_array_equal(arrays[name],value);assert arrays[name].dtype==value.dtype
  assert entry['points']==len(expected['physical_points']);summaries.append(entry)
else:raise ValueError('producer/reference required')
result={'scene':scene,'frames':summaries,'native_source_records':records,'native_source_points':points,'scope':'physical XYZ/intensity, native measurement identity and evaluation NLZ separated; no box inputs, packing, optimizer or quality claim'}
if mode=='reference':assert result==produced
Path('/outputs/report.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');Path('/outputs/resources.json').write_text(json.dumps({'elapsed_seconds':time.monotonic()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}));print('PASS selected detector physical frames',mode,scene,len(summaries),flush=True)
