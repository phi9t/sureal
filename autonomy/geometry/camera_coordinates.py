"""Reversible original-image to resized/padded coordinates.

Pixel centers use align_corners=False half-pixel geometry. Box coordinates are
continuous outer edges. Callers supply actual integer resized dimensions, not
an approximate common scale; interpolation/provenance remain separate gates.
"""
import numpy as np


def _geometry(original_hw,resized_hw,pad_xy):
    for hw in (original_hw,resized_hw):
        if len(hw)!=2 or any(type(x) is not int or x<=0 for x in hw):raise ValueError('positive integer image dimensions required')
    if len(pad_xy)!=2 or any(type(x) is not int or x<0 for x in pad_xy):raise ValueError('nonnegative integer left/top padding required')
    return np.array([resized_hw[1]/original_hw[1],resized_hw[0]/original_hw[0]]),np.array(pad_xy,dtype=float)


def pixel_centers(points,*,original_hw,resized_hw,pad_xy,inverse=False):
    scale,pad=_geometry(original_hw,resized_hw,pad_xy);x=np.asarray(points,dtype=np.float64)
    if x.ndim!=2 or x.shape[1]!=2 or not np.isfinite(x).all() or type(inverse) is not bool:raise ValueError('finite u/v centers and boolean direction required')
    return (x-pad+.5)/scale-.5 if inverse else (x+.5)*scale-.5+pad


def box_edges(boxes,*,original_hw,resized_hw,pad_xy,inverse=False):
    scale,pad=_geometry(original_hw,resized_hw,pad_xy);x=np.asarray(boxes,dtype=np.float64)
    if x.ndim!=2 or x.shape[1]!=4 or not np.isfinite(x).all() or np.any(x[:,2:]<x[:,:2]) or type(inverse) is not bool:raise ValueError('finite ordered umin/vmin/umax/vmax edges required')
    scale=np.tile(scale,2);pad=np.tile(pad,2)
    return (x-pad)/scale if inverse else x*scale+pad
