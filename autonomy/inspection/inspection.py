"""Inspection-only range/BEV mappings; every display keeps source identities."""
import numpy as np
from geometry.geometry_foundation import bev_indices


def bev_raster(xyz,*,lower=(-75,-75),upper=(75,75),cell=.5):
    xyz=np.asarray(xyz)
    cells,valid=bev_indices(xyz[:,:2],lower,upper,(cell,cell))
    shape=np.ceil((np.asarray(upper)-lower)/cell).astype(int)
    density=np.zeros((shape[1],shape[0]),dtype=np.int64)
    np.add.at(density,(shape[1]-1-cells[valid,1],cells[valid,0]),1)
    return density,{'retained':int(valid.sum()),'clipped':int((~valid).sum())}


def projection_samples(projection,camera,width,height,limit=5000):
    cp=np.asarray(projection).reshape(-1,2,3)
    valid=(cp[:,:,0]==camera)&(cp[:,:,1]>=0)&(cp[:,:,1]<width)&(cp[:,:,2]>=0)&(cp[:,:,2]<height)
    indexes,slots=np.nonzero(valid)
    if len(indexes)>limit:
        selection=np.linspace(0,len(indexes)-1,limit,dtype=int);indexes=indexes[selection];slots=slots[selection]
    return indexes,slots,cp[indexes,slots,1:]


def range_raster(pixels,ranges,shape):
    image=np.full(shape,np.nan)
    image[pixels[:,0],pixels[:,1]]=ranges
    return image
