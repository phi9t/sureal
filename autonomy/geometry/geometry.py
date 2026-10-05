"""Native Waymo range rays, following pinned upstream column/row conventions.

No TensorFlow dependency. XYZ is vehicle-reference meters. TOP compensation
uses world-from-acquisition pixel poses and inverse world-from-reference pose.
"""
import numpy as np
from .geometry_foundation import inverse, transform


def range_to_points(range_image, calibration, *, pixel_pose=None, frame_pose=None,
                    return_index, motion_policy):
    ri=np.asarray(range_image,dtype=np.float64)
    if ri.ndim!=3 or ri.shape[2]!=4 or min(ri.shape[:2])<1:raise ValueError('range shape')
    if return_index not in (1,2) or motion_policy not in ('uncompensated','compensated'):raise ValueError('return/motion policy')
    extrinsic=np.asarray(calibration['extrinsic'],dtype=np.float64).reshape(4,4)
    inverse(extrinsic)  # rigid/finite validation
    h,w=ri.shape[:2]
    incl=calibration.get('inclinations')
    if incl is None:
        lo,hi=calibration['inclination_min'],calibration['inclination_max']
        if not np.isfinite([lo,hi]).all() or lo>hi:raise ValueError('inclination bounds')
        incl=(np.arange(h)+.5)/h*(hi-lo)+lo
    incl=np.asarray(incl,dtype=np.float64)
    if incl.shape!=(h,) or not np.isfinite(incl).all():raise ValueError('inclinations')
    incl=incl[::-1]
    azimuth=((np.arange(w,0,-1)-.5)/w*2-1)*np.pi-np.arctan2(extrinsic[1,0],extrinsic[0,0])
    valid=np.isfinite(ri[...,0])&(ri[...,0]>0)
    pixels=np.argwhere(valid)
    rows,cols=pixels.T
    r=ri[rows,cols,0];e=incl[rows];a=azimuth[cols]
    xyz=np.column_stack((r*np.cos(e)*np.cos(a),r*np.cos(e)*np.sin(a),r*np.sin(e)))
    xyz=transform(extrinsic,xyz)
    if motion_policy=='compensated':
        if pixel_pose is None or frame_pose is None:raise ValueError('compensation requires pixel and frame poses')
        poses=np.asarray(pixel_pose,dtype=np.float64)
        if poses.shape!=(h,w,6) or not np.isfinite(poses).all():raise ValueError('pixel poses')
        selected=poses[rows,cols]
        roll,pitch,yaw=selected[:,:3].T
        # Rz(yaw) Ry(pitch) Rx(roll), matching upstream get_rotation_matrix.
        cr,sr=np.cos(roll),np.sin(roll);cp,sp=np.cos(pitch),np.sin(pitch);cy,sy=np.cos(yaw),np.sin(yaw)
        rot=np.stack((cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr,sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr,-sp,cp*sr,cp*cr),axis=1).reshape(-1,3,3)
        xyz=np.einsum('nij,nj->ni',rot,xyz)+selected[:,3:]
        xyz=transform(inverse(frame_pose),xyz)
    elif pixel_pose is not None or frame_pose is not None:
        raise ValueError('poses supplied to uncompensated policy')
    return {'xyz':xyz,'pixels':pixels,'physical_features':ri[rows,cols,:3],
            'return_index':return_index,'motion_policy':motion_policy,'range_shape':(h,w)}
