"""Masked Torch self-attention operator over lossless sparse BEV buckets."""
import torch
from torch import nn
from .sparse_windows import partition_sparse_windows


class SparseWindowAttention(nn.Module):
    """Grouping convention is explicit; output retains original token order.

    This operator omits positional encodings, residual/FFN blocks, multiscale
    fusion and diffusion. Those are separate architecture treatments. Grouping
    runs on host coordinates; host/device transfer cost belongs in later pilots.
    """
    def __init__(self,channels,heads,*,window_shape,shift):
        super().__init__()
        self.channels=channels;self.window_shape=window_shape;self.shift=shift
        self.attention=nn.MultiheadAttention(channels,heads,dropout=0,batch_first=True)

    def forward(self,features,coordinates):
        if (features.ndim!=2 or features.shape[1]!=self.channels
                or not features.is_floating_point() or not torch.isfinite(features).all()):
            raise ValueError('finite floating-point token features of declared width required')
        grouping=partition_sparse_windows(coordinates,window_shape=self.window_shape,shift=self.shift)
        if grouping['tokens']!=len(features):
            raise ValueError('coordinates and feature identities differ')
        if not len(features):return features.clone()
        output=torch.empty_like(features)
        for bucket in grouping['buckets'].values():
            indices=torch.as_tensor(bucket['token_indices'],device=features.device)
            valid=torch.as_tensor(bucket['valid_mask'],device=features.device)
            tokens=features[indices.clamp_min(0)]
            tokens=tokens.masked_fill(~valid.unsqueeze(-1),0)
            attended,_=self.attention(tokens,tokens,tokens,key_padding_mask=~valid,need_weights=False)
            output[indices[valid]]=attended[valid]
        return output
