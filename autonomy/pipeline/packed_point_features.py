"""Gather point features using retained packing provenance, never revoxelize."""
import torch

def packed_point_features(features,source_indices,counts):
    if (features.ndim!=2 or not features.is_floating_point() or features.shape[1]<=0
        or source_indices.ndim!=2 or counts.shape!=(len(source_indices),)
        or source_indices.dtype not in (torch.int32,torch.int64) or counts.dtype not in (torch.int32,torch.int64)
        or any(t.device!=features.device for t in (source_indices,counts)) or not torch.isfinite(features).all()):
        raise ValueError('finite point features and integer same-device packing provenance required')
    slots=source_indices.shape[1]
    if slots==0 or torch.any(counts<0) or torch.any(counts>slots):raise ValueError('invalid retained counts')
    valid=torch.arange(slots,device=features.device)[None,:]<counts[:,None]
    indices=source_indices[valid]
    if (torch.any(indices<0) or torch.any(indices>=len(features)) or torch.any(source_indices[~valid]!=-1)
        or len(torch.unique(indices))!=len(indices)):
        raise ValueError('forged, duplicate, or invalid retained source index')
    output=features.new_zeros((*source_indices.shape,features.shape[1]))
    output[valid]=features[indices]
    return output
