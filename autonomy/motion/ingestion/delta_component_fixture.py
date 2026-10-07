import pathlib,json,csv,subprocess,time,resource,sys,importlib.util
import numpy as np
from motion.ingestion.delta_components import decode_components
assert importlib.util.find_spec('tensorflow') is None
start=time.monotonic();records=[]
def digest(data):return int(subprocess.run(['/experiment/hash'],input=data,capture_output=True,check=True).stdout)
assert digest(b'')==14695981039346656037 and digest(b'hello')==0xa430d84680aabd0b
for split in ['training','validation']:
 root=pathlib.Path('/source')/split;rows=list(csv.DictReader((root/'components.tsv').open(),delimiter='\t'));assert len(rows)==121
 assert {(int(r['frame']),int(r['laser']),int(r['return'])) for r in rows if r['kind']=='range'}=={(f,l,r) for f in range(11) for l in range(1,6) for r in [1,2]}
 assert {(int(r['frame']),int(r['laser']),int(r['return'])) for r in rows if r['kind']=='pose'}=={(f,1,1) for f in range(11)}
 total=0;valid=0
 for row in rows:
  stem=root/row['stem'];meta=json.loads(stem.with_suffix('.json').read_text());mask=np.fromfile(stem.with_suffix('.mask.bin'),dtype='<u4');residual=np.fromfile(stem.with_suffix('.residual.bin'),dtype='<i8');decoded=decode_components(meta['shape'],meta['precision'],mask,residual);assert decoded.size==int(row['values']);assert np.count_nonzero(decoded[...,0]>0)==int(row['positive_channel0']);assert decoded.shape[-1]==(4 if row['kind']=='range' else 6);actual=digest(np.ascontiguousarray(decoded.transpose(2,0,1),dtype='<f8').tobytes());assert actual==int(row['channel_major_float64_fnv1a']);total+=decoded.size
  if row['kind']=='range':valid+=int(np.count_nonzero(decoded[...,0]>0))
 records.append({'split':split,'native_components':len(rows),'range_returns':110,'top_pixel_poses':11,'decoded_values':total,'positive_range_pixels':valid,'all_channel_major_float64_reference_hashes_match':True})
pathlib.Path('/outputs/check.json').write_text(json.dumps({'pilots':records,'tensorflow_absent':True,'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'full native historical delta decoding only; all4 range channels preserved but NLZ must not become physical features; XYZ/calibration/current-reference geometry pending'},indent=2));print('VERIFIED all242 native delta components')
