"""Explicit normalization-only diagnostic treatments; reference modules stay intact."""
import torch
from torch import nn

class PointChannelLayerNorm(nn.Module):
    """Normalize each point's channels, without mixing pillars or padded slots."""
    def __init__(self,channels,eps=1e-3):
        super().__init__();self.norm=nn.LayerNorm(channels,eps=eps)
    def forward(self,value):
        if value.ndim!=3:raise ValueError('pillar/channel/point layout required')
        return self.norm(value.transpose(1,2)).transpose(1,2)

def configure_norm(model,variant):
    if variant not in {'bn','gn_backbone','gn_backbone_ln_pillar','no_norm'}:
        raise ValueError('unknown normalization treatment')
    if variant=='bn':return model
    def replace(parent):
        for name,module in list(parent.named_children()):
            if isinstance(module,nn.BatchNorm2d):
                replacement=nn.Identity() if variant=='no_norm' else nn.GroupNorm(8,module.num_features,eps=module.eps,affine=True)
                setattr(parent,name,replacement)
            elif isinstance(module,nn.BatchNorm1d):
                if variant=='no_norm':setattr(parent,name,nn.Identity())
                elif variant=='gn_backbone_ln_pillar':setattr(parent,name,PointChannelLayerNorm(module.num_features,eps=module.eps))
            else:replace(module)
    replace(model);return model
