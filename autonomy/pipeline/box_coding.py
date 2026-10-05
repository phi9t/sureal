"""Metric box coding in native [x,y,center_z,length,width,height,yaw].

Explicit Waymo center-Z adaptation: dimensions are never treated as bottom-Z.
Yaw residuals remain additive; only decoded headings are canonicalized.
"""
import numpy as np


def _pair(value,anchors,*,physical):
    value=np.asarray(value,dtype=np.float64)
    anchors=np.asarray(anchors,dtype=np.float64)
    if value.ndim!=2 or value.shape[-1]!=7 or value.shape!=anchors.shape:
        raise ValueError('paired Nx7 native boxes required')
    if not np.isfinite(value).all() or not np.isfinite(anchors).all():
        raise ValueError('finite boxes required')
    if np.any(anchors[:,3:6]<=0) or (physical and np.any(value[:,3:6]<=0)):
        raise ValueError('positive physical dimensions required')
    return value,anchors


def encode_boxes(boxes,anchors):
    boxes,anchors=_pair(boxes,anchors,physical=True)
    diagonal=np.hypot(anchors[:,3],anchors[:,4])
    result=np.empty_like(boxes)
    result[:,:2]=(boxes[:,:2]-anchors[:,:2])/diagonal[:,None]
    result[:,2]=(boxes[:,2]-anchors[:,2])/anchors[:,5]
    result[:,3:6]=np.log(boxes[:,3:6]/anchors[:,3:6])
    result[:,6]=boxes[:,6]-anchors[:,6]
    if not np.isfinite(result).all():raise ValueError('nonfinite encoded box')
    return result


def decode_boxes(residuals,anchors):
    residuals,anchors=_pair(residuals,anchors,physical=False)
    diagonal=np.hypot(anchors[:,3],anchors[:,4])
    with np.errstate(over='ignore',under='ignore',invalid='ignore'):
        result=np.empty_like(residuals)
        result[:,:2]=residuals[:,:2]*diagonal[:,None]+anchors[:,:2]
        result[:,2]=residuals[:,2]*anchors[:,5]+anchors[:,2]
        result[:,3:6]=np.exp(residuals[:,3:6])*anchors[:,3:6]
        result[:,6]=(residuals[:,6]+anchors[:,6]+np.pi)%(2*np.pi)-np.pi
    if not np.isfinite(result).all() or np.any(result[:,3:6]<=0):
        raise ValueError('nonfinite or degenerate decoded box')
    return result


def direction_correct(yaw,bins):
    yaw=np.asarray(yaw,dtype=np.float64)
    bins=np.asarray(bins)
    if yaw.shape!=bins.shape or not np.isfinite(yaw).all() or bins.dtype.kind not in 'iu' or np.any((bins!=0)&(bins!=1)):
        raise ValueError('finite headings and paired binary direction bins required')
    corrected=yaw+np.where((yaw>0)!=(bins==1),np.pi,0.)
    return (corrected+np.pi)%(2*np.pi)-np.pi
