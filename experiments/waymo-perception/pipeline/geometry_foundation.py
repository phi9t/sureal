"""Float64 reference geometry: column vectors, right/body rotation-first twists.

This is a mathematical reference, not a dataset calibration adapter. Optical
camera depth is Z. BEV indices are (x-cell,y-cell), never display row/column.
"""
import numpy as np


def _array(value, shape=None):
    array = np.asarray(value, dtype=np.float64)
    if not np.isfinite(array).all() or (shape is not None and array.shape != shape):
        raise ValueError("nonfinite or wrong-shape geometry")
    return array


def skew(vector):
    x, y, z = _array(vector, (3,))
    return np.array([[0,-z,y],[z,0,-x],[-y,x,0]])


def _rotation(value):
    rotation = _array(value, (3,3))
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-8, rtol=0) or abs(np.linalg.det(rotation)-1)>1e-8:
        raise ValueError("not SO(3)")
    return rotation


def _pose(value):
    pose = _array(value, (4,4))
    _rotation(pose[:3,:3])
    if not np.allclose(pose[3], [0,0,0,1], atol=1e-10, rtol=0):
        raise ValueError("not SE(3)")
    return pose


def _coefficients(theta):
    t2 = theta*theta
    if theta < 1e-4:
        return (1-t2/6+t2*t2/120, .5-t2/24+t2*t2/720,
                1/6-t2/120+t2*t2/5040)
    return np.sin(theta)/theta, (1-np.cos(theta))/t2, (theta-np.sin(theta))/(theta*t2)


def so3_exp(omega):
    omega = _array(omega, (3,))
    hat = skew(omega)
    a,b,_ = _coefficients(np.linalg.norm(omega))
    return np.eye(3)+a*hat+b*(hat @ hat)


def so3_log(rotation):
    rotation = _rotation(rotation)
    vee = np.array([rotation[2,1]-rotation[1,2],rotation[0,2]-rotation[2,0],rotation[1,0]-rotation[0,1]])/2
    theta = np.arctan2(np.linalg.norm(vee), np.clip((np.trace(rotation)-1)/2,-1,1))
    if theta < 1e-7:
        return vee*(1+theta*theta/6)
    if np.pi-theta < 1e-6:
        # Eigenvector is stable where the antisymmetric part approaches zero.
        _, vectors = np.linalg.eigh((rotation+rotation.T)/2)
        axis = vectors[:,-1]
        if np.dot(axis,vee)<0:
            axis = -axis
        return theta*axis
    return theta/np.sin(theta)*vee


def so3_left_jacobian(omega):
    omega = _array(omega, (3,))
    hat = skew(omega)
    _,b,c = _coefficients(np.linalg.norm(omega))
    return np.eye(3)+b*hat+c*(hat @ hat)


def se3_exp(xi):
    xi = _array(xi, (6,))
    pose = np.eye(4)
    pose[:3,:3] = so3_exp(xi[:3])
    pose[:3,3] = so3_left_jacobian(xi[:3]) @ xi[3:]
    return pose


def se3_log(pose):
    pose = _pose(pose)
    omega = so3_log(pose[:3,:3])
    return np.concatenate([omega,np.linalg.solve(so3_left_jacobian(omega),pose[:3,3])])


def inverse(pose):
    pose = _pose(pose)
    result = np.eye(4)
    result[:3,:3] = pose[:3,:3].T
    result[:3,3] = -result[:3,:3] @ pose[:3,3]
    return result


def transform(pose, points):
    pose = _pose(pose)
    points = _array(points)
    if points.ndim not in (1,2) or points.shape[-1]!=3:
        raise ValueError("points must be (...,3)")
    return points @ pose[:3,:3].T+pose[:3,3]


def adjoint(pose):
    pose = _pose(pose)
    result = np.zeros((6,6))
    result[:3,:3] = result[3:,3:] = pose[:3,:3]
    result[3:,:3] = skew(pose[:3,3]) @ pose[:3,:3]
    return result


def point_jacobian(pose, point):
    pose = _pose(pose)
    return pose[:3,:3] @ np.column_stack([-skew(point),np.eye(3)])


def polar_to_cartesian(polar):
    polar = _array(polar)
    if polar.ndim not in (1,2) or polar.shape[-1]!=3 or (polar[...,0]<0).any():
        raise ValueError("polar must be nonnegative range, azimuth, elevation")
    r,a,b = np.moveaxis(polar,-1,0)
    return np.stack([r*np.cos(b)*np.cos(a),r*np.cos(b)*np.sin(a),r*np.sin(b)],axis=-1)


def cartesian_to_polar(points):
    points = _array(points)
    if points.ndim not in (1,2) or points.shape[-1]!=3:
        raise ValueError("points must be (...,3)")
    x,y,z = np.moveaxis(points,-1,0)
    horizontal = np.hypot(x,y)
    ranges = np.hypot(horizontal,z)
    azimuth = np.where(horizontal>0,np.arctan2(y,x),np.nan)
    elevation = np.where(ranges>0,np.arctan2(z,horizontal),np.nan)
    return np.stack([ranges,azimuth,elevation],axis=-1), (horizontal>0)&(ranges>0)


def polar_jacobian(polar):
    r,a,b = _array(polar, (3,))
    if r<0: raise ValueError("negative range")
    ca,sa,cb,sb = np.cos(a),np.sin(a),np.cos(b),np.sin(b)
    return np.array([[cb*ca,-r*cb*sa,-r*sb*ca],
                     [cb*sa,r*cb*ca,-r*sb*sa],[sb,0,r*cb]])


def bev_indices(points_xy, minimum, maximum, resolution):
    points = _array(points_xy)
    minimum,maximum,resolution = [_array(v,(2,)) for v in (minimum,maximum,resolution)]
    if points.ndim!=2 or points.shape[1]!=2 or (resolution<=0).any() or (maximum<=minimum).any():
        raise ValueError("invalid BEV grid")
    valid = ((points>=minimum)&(points<maximum)).all(axis=1)
    indices = np.full(points.shape,-1,dtype=np.int64)
    dimensions = np.ceil((maximum-minimum)/resolution).astype(np.int64)
    # A mathematically interior value can round onto the upper quotient edge.
    indices[valid] = np.minimum(
        np.floor((points[valid]-minimum)/resolution).astype(np.int64), dimensions-1)
    return indices,valid


def pinhole_project(points_optical, intrinsics):
    points = _array(points_optical)
    fx,fy,cx,cy = _array(intrinsics,(4,))
    if points.ndim!=2 or points.shape[1]!=3 or fx<=0 or fy<=0:
        raise ValueError("invalid optical-camera projection")
    valid = points[:,2]>0
    uv = np.full((len(points),2),np.nan)
    uv[valid] = points[valid,:2]/points[valid,2,None]*[fx,fy]+[cx,cy]
    return uv,valid


def radar_radial_velocity(position, target_velocity, sensor_velocity):
    position = _array(position,(3,))
    radius = np.linalg.norm(position)
    if radius==0: raise ValueError("undefined radar ray")
    relative = _array(target_velocity,(3,))-_array(sensor_velocity,(3,))
    return float(position @ relative/radius)


def transport_covariance(jacobian, covariance):
    """Local linear covariance; caller owns independence/cross-term assumptions."""
    jacobian, covariance = _array(jacobian), _array(covariance)
    if (jacobian.ndim!=2 or covariance.shape!=(jacobian.shape[1],jacobian.shape[1])
            or not np.allclose(covariance,covariance.T,atol=1e-12,rtol=0)
            or np.linalg.eigvalsh(covariance).min() < 0):
        raise ValueError("invalid covariance")
    covariance = (covariance+covariance.T)/2
    return jacobian @ covariance @ jacobian.T


def sensor_to_reference(points, vehicle_from_sensor, world_from_acquisition,
                        world_from_reference):
    """Static extrinsic and explicitly timestamped acquisition/reference poses."""
    chain = inverse(world_from_reference) @ _pose(world_from_acquisition) @ _pose(vehicle_from_sensor)
    return transform(chain,points)
