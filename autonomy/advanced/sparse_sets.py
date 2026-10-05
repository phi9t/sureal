"""Explicit occupied-token sets and deterministic segmented spatial pooling."""
import numpy as np
import torch


def coordinates_array(coordinates):
 if coordinates.ndim!=2 or coordinates.shape[1]!=4 or coordinates.dtype not in (torch.int32,torch.int64) or len(coordinates)==0:raise ValueError('nonempty integer batch/z/y/x coordinates required')
 values=coordinates.detach().cpu().numpy()
 if np.any(values<0) or np.any(values[:,1]!=0) or len(np.unique(values,axis=0))!=len(values):raise ValueError('unique nonnegative XY tokens required')
 return values

def window_sets(coordinates,*,window=8,max_tokens=64,shift=0,axis='x'):
 values=coordinates_array(coordinates)
 if type(window) is not int or window<=0 or type(max_tokens) is not int or max_tokens<=0 or type(shift) is not int or not 0<=shift<window or axis not in ('x','y'):raise ValueError('valid sparse window configuration required')
 groups={}
 for i,(batch,_,y,x) in enumerate(values):groups.setdefault((int(batch),(int(y)-shift)//window,(int(x)-shift)//window),[]).append(i)
 chunks=[]
 for key in sorted(groups):
  ids=sorted(groups[key],key=lambda i:(int(values[i,3]),int(values[i,2])) if axis=='x' else (int(values[i,2]),int(values[i,3])))
  for start in range(0,len(ids),max_tokens):chunks.append(ids[start:start+max_tokens])
 indices=np.full((len(chunks),max_tokens),-1,dtype=np.int64)
 for row,ids in enumerate(chunks):indices[row,:len(ids)]=ids
 result=torch.from_numpy(indices).to(coordinates.device);return result,result>=0

def pool_tokens(features,coordinates):
 values=coordinates_array(coordinates)
 if features.ndim!=2 or len(features)!=len(values) or not features.is_floating_point() or features.device!=coordinates.device:raise ValueError('aligned physical token features required')
 coarse=values.copy();coarse[:,2:]//=2;unique,inverse=np.unique(coarse,axis=0,return_inverse=True);order=np.argsort(inverse,kind='stable');lengths=np.bincount(inverse,minlength=len(unique));index=torch.from_numpy(order).to(features.device);counts=torch.from_numpy(lengths).to(features.device)
 return torch.segment_reduce(features[index],reduce='mean',lengths=counts),torch.from_numpy(unique).to(coordinates.device)
