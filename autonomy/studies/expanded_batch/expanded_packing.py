"""Case-specific physical-only grouping and native range observation identities."""
import numpy as np
from detection.pillar_packing import pack_points

ROI=(-64.,-64.,-4.,64.,64.,6.)

def pack_case(points,name,*,seed,pillar_cap=20000):
 cell={'grid_fine':.125,'grid_coarse':.5,'ragged_pillars':.25}.get(name)
 if cell is None:raise ValueError('unknown grouping treatment')
 if name!='ragged_pillars':return pack_points(points,roi=ROI,cell_size=(cell,cell),max_points=32,max_pillars=pillar_cap,seed=seed)
 points=np.asarray(points)
 if points.ndim!=2 or points.shape[1]!=4 or points.dtype.kind!='f' or not np.isfinite(points).all() or type(pillar_cap) is not int or pillar_cap<=0 or type(seed) is not int or seed<0:raise ValueError('finite physical points and positive cap required')
 roi=np.asarray(ROI);eligible=np.flatnonzero(np.all((points[:,:3]>=roi[:3])&(points[:,:3]<roi[3:]),axis=1));xy=np.minimum(np.floor((points[eligible,:2]-roi[:2])/cell).astype(np.int64),511);keys=xy[:,1]*512+xy[:,0];order=np.argsort(keys,kind='stable');unique,starts,lengths=np.unique(keys[order],return_index=True,return_counts=True);chosen=np.arange(len(unique))
 if len(chosen)>pillar_cap:chosen=np.sort(np.random.default_rng(seed).choice(chosen,pillar_cap,replace=False))
 ids=np.concatenate([eligible[order[starts[i]:starts[i]+lengths[i]]] for i in chosen]) if len(chosen) else np.empty(0,dtype=np.int64);counts=lengths[chosen];coords=np.zeros((len(chosen),4),dtype=np.int64);coords[:,2]=unique[chosen]//512;coords[:,3]=unique[chosen]%512
 report={'input_points':len(points),'eligible_points':len(eligible),'outside_roi':len(points)-len(eligible),'eligible_pillars':len(unique),'retained_pillars':len(chosen),'pillar_limit_dropped_points':len(eligible)-len(ids),'point_limit_dropped_points':0,'retained_points':len(ids)}
 return {'points':points[ids],'counts':counts,'coordinates':coords,'source_indices':ids,'counts_report':report,'grid':[512,512]}

def range_observations(grids,physical,identity,source_indices):
 physical=np.asarray(physical);identity=np.asarray(identity);indices=np.asarray(source_indices)
 keys=[(l,r) for l in range(1,6) for r in (1,2)]
 if set(grids)!=set(keys) or physical.ndim!=2 or physical.shape[1]!=4 or identity.shape!=(len(physical),4) or identity.dtype.kind not in 'iu' or indices.dtype.kind not in 'iu' or np.any(indices < -1) or np.any(indices>=len(physical)):raise ValueError('full native grids and aligned physical identities required')
 if not np.isfinite(physical).all() or len(np.unique(identity,axis=0))!=len(identity):raise ValueError('finite physical points and unique identities required')
 result={};point_pixels=np.full((len(physical),3),-1,dtype=np.int64)
 for number,(laser,ret) in enumerate(keys):
  raw=grids[laser,ret];mask=(identity[:,0]==laser)&(identity[:,1]==ret)
  if raw is None:
   if mask.any():raise ValueError('absent return has physical points')
   continue
  raw=np.asarray(raw)
  if raw.ndim!=3 or raw.shape[-1]!=4 or min(raw.shape[:2])<=0:raise ValueError('native four-channel range shape required')
  valid=raw[:,:,0]>0;pixels=identity[mask,2:];h,w=valid.shape
  if not np.isfinite(raw[:,:,:3][valid]).all() or len(pixels)!=int(valid.sum()) or np.any(pixels<0) or np.any(pixels[:,0]>=h) or np.any(pixels[:,1]>=w):raise ValueError('range point coverage or physical channels differ')
  expected=np.argwhere(valid);sort=np.lexsort((pixels[:,1],pixels[:,0]))
  if not np.array_equal(pixels[sort],expected) or not np.array_equal(raw[pixels[:,0],pixels[:,1],1],physical[mask,3]):raise ValueError('range pixel identity or intensity differs')
  measurements=np.where(valid[:,:,None],raw[:,:,:3],0).astype(np.float32)
  result[f'range_raw_{laser}_{ret}']=measurements.transpose(2,0,1)[None];result[f'range_valid_{laser}_{ret}']=valid[None];point_pixels[mask]=np.column_stack((np.full(len(pixels),number),pixels))
 if np.any(point_pixels[:,0]<0):raise ValueError('unknown physical sensor identity')
 gathered=np.full((*indices.shape,3),-1,dtype=np.int64);kept=indices>=0;gathered[kept]=point_pixels[indices[kept]];result['range_pixels']=gathered
 return result
