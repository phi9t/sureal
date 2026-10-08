"""Bounded native physical point packing with explicit retained-source indices."""
import numpy as np


def pack_points(points,*,roi,cell_size,max_pillars,max_points,seed):
    points=np.asarray(points)
    roi=np.asarray(roi,dtype=np.float64);cell=np.asarray(cell_size,dtype=np.float64)
    if points.ndim!=2 or points.shape[1]!=4 or points.dtype.kind!='f' or not np.isfinite(points).all():
        raise ValueError('finite Nx4 physical XYZ/intensity required')
    if roi.shape!=(6,) or cell.shape!=(2,) or not np.isfinite(roi).all() or not np.isfinite(cell).all() or np.any(cell<=0) or np.any(roi[3:]<=roi[:3]):
        raise ValueError('finite ordered ROI and positive XY cell size required')
    if type(max_pillars) is not int or type(max_points) is not int or min(max_pillars,max_points)<=0 or type(seed) is not int or seed<0:
        raise ValueError('positive packing limits and nonnegative integer seed required')
    grid=(roi[3:5]-roi[:2])/cell
    if not np.allclose(grid,np.rint(grid),rtol=0,atol=1e-9) or np.any(grid>2**30):
        raise ValueError('bounded integer XY grid required')
    nx,ny=np.rint(grid).astype(np.int64)
    eligible=np.flatnonzero(np.all((points[:,:3]>=roi[:3])&(points[:,:3]<roi[3:]),axis=1))
    xy=np.floor((points[eligible,:2]-roi[:2])/cell).astype(np.int64)
    # Roundoff at the upper edge must never create an out-of-grid scatter cell.
    xy=np.minimum(xy,np.array([nx-1,ny-1]))
    keys=xy[:,1]*nx+xy[:,0]
    order=np.argsort(keys,kind='stable');ordered=keys[order]
    unique,starts,counts=np.unique(ordered,return_index=True,return_counts=True)
    rng=np.random.default_rng(seed)
    selected=np.arange(len(unique))
    if len(selected)>max_pillars:selected=np.sort(rng.choice(selected,size=max_pillars,replace=False))
    size=len(selected);packed=np.zeros((size,max_points,4),dtype=points.dtype)
    indices=np.full((size,max_points),-1,dtype=np.int64);valid_counts=np.zeros(size,dtype=np.int64)
    coordinates=np.zeros((size,4),dtype=np.int64);dropped_points=0
    for row,group in enumerate(selected):
        source=eligible[order[starts[group]:starts[group]+counts[group]]]
        if len(source)>max_points:
            dropped_points+=len(source)-max_points
            source=source[np.sort(rng.choice(len(source),size=max_points,replace=False))]
        length=len(source);packed[row,:length]=points[source];indices[row,:length]=source;valid_counts[row]=length
        coordinates[row,2:]=[unique[group]//nx,unique[group]%nx]
    retained=int(valid_counts.sum());pillar_dropped=int(len(eligible)-counts[selected].sum())
    report={'input_points':len(points),'outside_roi':len(points)-len(eligible),
            'eligible_points':len(eligible),'eligible_pillars':len(unique),
            'retained_pillars':size,'pillar_limit_dropped_points':pillar_dropped,
            'point_limit_dropped_points':dropped_points,'retained_points':retained}
    assert report['outside_roi']+pillar_dropped+dropped_points+retained==len(points)
    return {'points':packed,'counts':valid_counts,'coordinates':coordinates,
            'source_indices':indices,'counts_report':report,
            'sampling':'seeded NumPy PCG64; sampled cell IDs sorted; sampled original indices retain order',
            'seed':seed,'grid':[int(nx),int(ny)]}
