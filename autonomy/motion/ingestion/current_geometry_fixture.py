import pathlib,json,csv,time,resource,importlib.util
import numpy as np
from motion.ingestion.delta_components import decode_components
from geometry.geometry import range_to_points
from geometry.geometry_foundation import inverse,transform
assert importlib.util.find_spec('tensorflow') is None
names={'TOP':1,'FRONT':2,'SIDE_LEFT':3,'SIDE_RIGHT':4,'REAR':5};start=time.monotonic();reports=[]
def decoded(root,stem):
 p=root/stem;m=json.loads(p.with_suffix('.json').read_text());return decode_components(m['shape'],m['precision'],np.fromfile(p.with_suffix('.mask.bin'),dtype='<u4'),np.fromfile(p.with_suffix('.residual.bin'),dtype='<i8'))
for split in ['training','validation']:
 root=pathlib.Path('/source')/split;meta=json.loads(pathlib.Path('/experiment',split+'-metadata.json').read_text());assert meta['current_time_index']==10 and len(meta['timestamps_seconds'])==11;frames=meta['compressed_frame_laser_data'];current=np.asarray(frames[10]['pose']['transform']).reshape(4,4);inverse(current);out=pathlib.Path('/outputs')/split;out.mkdir();rows=list(csv.DictReader((root/'components.tsv').open(),delimiter='\t'));manifest=[]
 for row in rows:
  if row['kind']!='range':continue
  i,l,r=map(int,[row['frame'],row['laser'],row['return']]);frame=frames[i];calibs={names[c['name']]:c for c in frame['laser_calibrations']};assert len(calibs)==5;c=calibs[l];calib={'extrinsic':c['extrinsic']['transform']};incl=c.get('beam_inclinations')
  if incl:calib['inclinations']=incl
  else:calib.update({'inclination_min':c['beam_inclination_min'],'inclination_max':c['beam_inclination_max']})
  image=decoded(root,row['stem']);pose=np.asarray(frame['pose']['transform']).reshape(4,4)
  if l==1:result=range_to_points(image,calib,pixel_pose=decoded(root,f'{i}-1-1-pose'),frame_pose=pose,return_index=r,motion_policy='compensated')
  else:result=range_to_points(image,calib,return_index=r,motion_policy='uncompensated')
  xyz=transform(inverse(current)@pose,result['xyz']);assert np.isfinite(xyz).all();assert len(xyz)==int(row['positive_channel0']);stem=out/row['stem'];xyz.astype('<f8').tofile(stem.with_suffix('.xyz.bin'));result['pixels'].astype('<i4').tofile(stem.with_suffix('.pixels.bin'));result['physical_features'].astype('<f4').tofile(stem.with_suffix('.features.bin'));manifest.append({'frame':i,'timestamp_seconds':meta['timestamps_seconds'][i],'laser':l,'return':r,'stem':row['stem'],'points':len(xyz),'shape':list(image.shape),'physical_features':'range,intensity,elongation only; NLZ excluded','reference':'vehicle frame at current index10','pixel_pose_return':1 if l==1 else None})
 (out/'manifest.json').write_text(json.dumps({'scenario_id':meta['scenario_id'],'records':manifest},indent=2));reports.append({'split':split,'scenario_id':meta['scenario_id'],'range_returns':len(manifest),'points':sum(x['points'] for x in manifest),'no_roi_or_point_cap':True})
pathlib.Path('/outputs/check.json').write_text(json.dumps({'pilots':reports,'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'tensorflow_absent':True,'scope':'producer current-reference XYZ/ray keys/physical features; independent native scalar geometry verification pending'},indent=2));print('PRODUCED all native positive-range XYZ')
