"""Bounded physical-only detector frame assembly with separate measurement/eval keys."""
import numpy as np

def assemble_frame(records,*,scene,timestamp):
 if type(timestamp) is not int or timestamp<0:raise ValueError('native frame identity required')
 index={}
 for record in records:
  d=record['identity'];key=(d['laser'],d['return'])
  if d['context']!=scene or d['timestamp']!=timestamp or key in index or key[0] not in range(1,6) or key[1] not in (1,2) or d['motion']!=('compensated' if key[0]==1 else 'uncompensated'):raise ValueError('duplicate or incompatible measurement identity')
  index[key]=record
 if set(index)!={(l,r) for l in range(1,6) for r in (1,2)}:raise ValueError('all native sensor/return states required')
 physical=[];identities=[];evaluation=[];states=[]
 for (laser,ret),record in sorted(index.items()):
  present=record['return_present']
  if type(present) is not bool:raise ValueError('explicit return-presence state required')
  if not present:
   if record['observations'] or record['targets'] or record['evaluation']:raise ValueError('absent return carries payload')
   states.append([laser,ret,0,0]);continue
  obs=record['observations'];xyz=np.asarray(obs['xyz']);features=np.asarray(obs['physical_features']);pixels=np.asarray(record['identity']['pixels']);nlz=np.asarray(record['evaluation']['nlz']);n=len(xyz)
  if xyz.shape!=(n,3) or features.shape!=(n,3) or pixels.shape!=(n,2) or nlz.shape!=(n,) or xyz.dtype.kind!='f' or features.dtype.kind!='f' or pixels.dtype.kind not in 'iu' or not np.isfinite(xyz).all() or not np.isfinite(features).all() or np.any(features[:,0]<=0) or np.any(pixels<0) or not np.isin(nlz,[-1,1]).all():raise ValueError('native physical/identity/evaluation alignment differs')
  if len(set(map(tuple,pixels.tolist())))!=n:raise ValueError('duplicate return pixel')
  physical.append(np.column_stack((xyz,features[:,1])).astype(np.float64));identities.append(np.column_stack((np.full(n,laser,dtype=np.int64),np.full(n,ret,dtype=np.int64),pixels)).astype(np.int64));evaluation.append(nlz.astype(np.int64));states.append([laser,ret,1,n])
 return {'physical_points':np.concatenate(physical) if physical else np.empty((0,4),dtype=np.float64),'measurement_identity':np.concatenate(identities) if identities else np.empty((0,4),dtype=np.int64),'evaluation_nlz':np.concatenate(evaluation) if evaluation else np.empty((0,),dtype=np.int64),'return_states':np.asarray(states,dtype=np.int64)}
