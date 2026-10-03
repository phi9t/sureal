"""Native semantic IoU and paired whole-segment bootstrap.

Matrices are seed x segment x truth-ID x prediction-ID, using native LiDAR
IDs 0..22. Seed means are kept paired, and each draw resamples whole segments
with identical indices across treatments and seeds. Caller must separately
verify original point identities; class-support counts cannot prove identity.
"""
import numpy as np


def _counts(value):
    value=np.asarray(value)
    if value.shape[-2:]!=(23,23) or value.dtype.kind not in 'iu' or np.any(value<0):raise ValueError('native nonnegative integer confusion matrices required')
    return value


def _mean_iou(value):
    valid=value[...,1:,1:]
    intersection=np.diagonal(valid,axis1=-2,axis2=-1)
    union=value[...,1:,:].sum(axis=-1)+valid.sum(axis=-2)-intersection
    iou=np.ones(intersection.shape,dtype=np.float64)
    np.divide(intersection,union,out=iou,where=union>0)
    return iou.mean(axis=-1)


def native_semantic_iou(confusion):
    confusion=_counts(confusion)
    if confusion.ndim!=2:raise ValueError('one confusion matrix required')
    return float(_mean_iou(confusion))


def paired_segment_bootstrap(baseline,treatment,replicates=10000,seed=20260930):
    baseline=_counts(baseline);treatment=_counts(treatment)
    if baseline.ndim!=4 or treatment.shape!=baseline.shape or baseline.shape[0]<1 or baseline.shape[1]<2:raise ValueError('paired seed/segment matrix shapes required')
    if not np.array_equal(baseline.sum(axis=-1)[...,1:],treatment.sum(axis=-1)[...,1:]):raise ValueError('different eligible class support')
    if baseline[...,1:,:].sum()==0:raise ValueError('no eligible groundtruth support')
    if type(replicates) is not int or not 1<=replicates<=1000000:raise ValueError('replicate count')
    rng=np.random.default_rng(seed);effects=[]
    for start in range(0,replicates,128):
        indices=rng.integers(0,baseline.shape[1],size=(min(128,replicates-start),baseline.shape[1]))
        base=_mean_iou(baseline[:,indices].sum(axis=2))
        other=_mean_iou(treatment[:,indices].sum(axis=2))
        effects.extend((other-base).mean(axis=0).tolist())
    seed_effects=_mean_iou(treatment.sum(axis=1))-_mean_iou(baseline.sum(axis=1))
    return {'effect':float(seed_effects.mean()),'seed_effects':seed_effects.tolist(),
            'interval_95':np.quantile(effects,[.025,.975],method='linear').tolist(),
            'segments':baseline.shape[1],'seeds':baseline.shape[0],'replicates':replicates,'bootstrap_seed':seed,
            'unit':'whole segment; seed effects paired, segment draws shared across seeds'}
