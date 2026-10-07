"""Candidate full-support range U-Net; separate semantics and detection gate."""
import torch
from torch import nn
from torch.nn import functional as F

class Block(nn.Sequential):
    def __init__(self,inputs,outputs):
        super().__init__(nn.Conv2d(inputs,outputs,3,padding=1,bias=False),nn.GroupNorm(8,outputs),nn.ReLU(),
                         nn.Conv2d(outputs,outputs,3,padding=1,bias=False),nn.GroupNorm(8,outputs),nn.ReLU())

class RangeFrontend(nn.Module):
    """Untrained SUREAL candidate, not a reproduction of the RSN architecture.

    Raw range/intensity/elongation only. Masks govern observation support;
    semantic labels, box-derived gates and NLZ never enter the forward inputs.
    Widths32/64/128 and zero angular boundary padding are candidate choices.
    """
    def __init__(self):
        super().__init__()
        self.register_buffer('channel_maxima',torch.tensor([79.5,2.,2.]).reshape(1,3,1,1))
        self.first=Block(3,32);self.second=Block(32,64);self.third=Block(64,128)
        self.up_second=Block(192,64);self.up_first=Block(96,32)
        self.semantic=nn.Conv2d(32,23,1);self.foreground=nn.Conv2d(32,1,1)
    def forward(self,raw,valid):
        if (raw.ndim!=4 or raw.shape[1]!=3 or not raw.is_floating_point()
            or valid.shape!=(raw.shape[0],raw.shape[2],raw.shape[3]) or valid.dtype!=torch.bool
            or valid.device!=raw.device or min(raw.shape[2:])<2 or not torch.isfinite(raw).all()):
            raise ValueError('finite B3HW physical measurements and boolean BHW mask required')
        mask=valid[:,None]
        normalized=torch.clamp(raw/self.channel_maxima.to(dtype=raw.dtype),0,1)*mask
        first=self.first(normalized)
        second=self.second(F.max_pool2d(first,2,ceil_mode=True))
        third=self.third(F.max_pool2d(second,2,ceil_mode=True))
        up=self.up_second(torch.cat([F.interpolate(third,size=second.shape[-2:],mode='bilinear',align_corners=False),second],dim=1))
        features=self.up_first(torch.cat([F.interpolate(up,size=first.shape[-2:],mode='bilinear',align_corners=False),first],dim=1))
        return {'features':features*mask,'semantic_logits':self.semantic(features)*mask,'foreground_logits':self.foreground(features)*mask}
