"""Candidate range-augmented PFN and unchanged shared anchor detection head."""
import torch
from torch import nn
from .pillar_encoder import scatter

class RangePillarFeatureNet(nn.Module):
    def __init__(self,range_channels):
        super().__init__()
        if type(range_channels) is not int or range_channels<=0:raise ValueError('positive feature-channel count required')
        self.range_channels=range_channels
        self.linear=nn.Linear(9+range_channels,64,bias=False)
        self.norm=nn.BatchNorm1d(64,eps=1e-3,momentum=.01)
    def forward(self,decorated,range_features,counts):
        if (decorated.ndim!=3 or decorated.shape[-1]!=9 or min(decorated.shape[:2])<=0
            or range_features.shape!=(*decorated.shape[:2],self.range_channels)
            or counts.shape!=(len(decorated),) or counts.dtype not in (torch.int32,torch.int64)
            or any(t.device!=decorated.device for t in (range_features,counts))
            or not decorated.is_floating_point() or range_features.dtype!=decorated.dtype
            or torch.any(counts<=0) or torch.any(counts>decorated.shape[1])):
            raise ValueError('aligned physical decorations, gathered features and integer retained counts required')
        valid=torch.arange(decorated.shape[1],device=decorated.device)[None,:]<counts[:,None]
        combined=torch.cat([decorated,range_features],dim=-1)
        if not torch.isfinite(combined[valid]).all():raise ValueError('nonfinite valid point features')
        combined=torch.where(valid[:,:,None],combined,torch.zeros_like(combined))
        # Same source-compatible BN/max padding policy as the physical PFN.
        return torch.relu(self.norm(self.linear(combined).transpose(1,2))).amax(2)

class SharedPillarHead(nn.Module):
    """Reuse actual detector head modules; original encoder remains separate."""
    def __init__(self,detector):
        super().__init__()
        self.nx,self.ny=detector.nx,detector.ny
        self.classes,self.anchors_per_cell=detector.classes,detector.anchors_per_cell
        self.blocks,self.upsample=detector.blocks,detector.upsample
        self.class_head,self.box_head,self.direction_head=detector.class_head,detector.box_head,detector.direction_head
    def forward(self,pillar_features,coordinates,*,batch_size):
        image=scatter(pillar_features,coordinates,batch_size=batch_size,nx=self.nx,ny=self.ny)
        parts=[]
        for block,up in zip(self.blocks,self.upsample):
            image=block(image);parts.append(up(image))
        features=torch.cat(parts,dim=1)
        def flatten(head,width):
            return head(features).permute(0,2,3,1).contiguous().reshape(batch_size,-1,width)
        return {'classification':flatten(self.class_head,self.classes),'box_residuals':flatten(self.box_head,7),'direction':flatten(self.direction_head,2)}
