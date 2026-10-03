"""Stride-two metric anchor centers aligned with row/column/anchor head order."""
import numpy as np


def anchor_grid(*,nx,ny,cell_size,origin,templates):
    # Template order is length,width,height,center_z,yaw; no bottom-Z conversion.
    cell=np.asarray(cell_size,dtype=np.float64);origin=np.asarray(origin,dtype=np.float64)
    templates=np.asarray(templates,dtype=np.float64)
    if type(nx) is not int or type(ny) is not int or min(nx,ny)<=0 or nx%2 or ny%2:
        raise ValueError('positive even XY grid required')
    if cell.shape!=(2,) or origin.shape!=(2,) or not np.isfinite(cell).all() or not np.isfinite(origin).all() or np.any(cell<=0):
        raise ValueError('finite metric origin and positive cell sizes required')
    if templates.ndim!=2 or templates.shape[1]!=5 or not len(templates) or not np.isfinite(templates).all() or np.any(templates[:,:3]<=0):
        raise ValueError('positive native LWH/center-Z/yaw templates required')
    y,x=np.meshgrid(np.arange(ny//2),np.arange(nx//2),indexing='ij')
    result=np.empty((ny//2,nx//2,len(templates),7),dtype=np.float64)
    result[...,0]=(origin[0]+(2*x+1)*cell[0])[:,:,None]
    result[...,1]=(origin[1]+(2*y+1)*cell[1])[:,:,None]
    result[...,2]=templates[:,3]
    result[...,3:6]=templates[:,:3]
    result[...,6]=templates[:,4]
    return result.reshape(-1,7)
