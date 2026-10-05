"""PointPillars nine-channel core; upstream padding/BN policy, no sampling."""
import math
import torch
from torch import nn


def decorate(points, counts, coordinates, *, cell_size, origin):
    if points.ndim != 3 or points.shape[-1] != 4 or not points.is_floating_point():
        raise ValueError('physical XYZ/intensity tensor required')
    n, slots, _ = points.shape
    if counts.shape != (n,) or coordinates.shape != (n,4):
        raise ValueError('counts or batch/z/y/x coordinates differ')
    if counts.dtype not in (torch.int32,torch.int64) or coordinates.dtype not in (torch.int32,torch.int64):
        raise ValueError('integer counts and coordinates required')
    if any(t.device != points.device for t in (counts,coordinates)):
        raise ValueError('tensor devices differ')
    if len(cell_size)!=2 or len(origin)!=2 or any(not math.isfinite(v) for v in (*cell_size,*origin)) or min(cell_size)<=0:
        raise ValueError('finite positive metric grid required')
    if n == 0 or slots == 0 or torch.any(counts<=0) or torch.any(counts>slots):
        raise ValueError('nonempty pillars and valid counts required')
    if torch.any(coordinates<0) or torch.any(coordinates[:,1]!=0):
        raise ValueError('nonnegative XY pillar coordinates required')
    valid = torch.arange(slots,device=points.device)[None,:] < counts[:,None]
    if not torch.isfinite(points[valid]).all():
        raise ValueError('nonfinite measured observation')
    clean = torch.where(valid[:,:,None],points,torch.zeros_like(points))
    mean = clean[:,:,:3].sum(1,keepdim=True)/counts[:,None,None]
    cluster = clean[:,:,:3]-mean
    center = torch.stack(((coordinates[:,3]+0.5)*cell_size[0]+origin[0],
                          (coordinates[:,2]+0.5)*cell_size[1]+origin[1]),dim=-1).to(points.dtype)
    decorated = torch.cat((clean,cluster,clean[:,:,:2]-center[:,None,:]),dim=-1)
    return torch.where(valid[:,:,None],decorated,torch.zeros_like(decorated))


class PillarFeatureNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(9,64,bias=False)
        self.norm = nn.BatchNorm1d(64,eps=1e-3,momentum=0.01)

    def forward(self, decorated):
        if decorated.ndim!=3 or decorated.shape[-1]!=9 or min(decorated.shape[:2])<=0:
            raise ValueError('nonempty nine-channel decorations required')
        # Source-compatible BN includes padded slots; do not remask after ReLU.
        features = self.linear(decorated).transpose(1,2)
        return torch.relu(self.norm(features)).amax(dim=2)


def scatter(features, coordinates, *, batch_size, nx, ny):
    if min(batch_size,nx,ny)<=0 or features.ndim!=2 or coordinates.shape!=(features.shape[0],4):
        raise ValueError('valid dense grid and pillar features required')
    if coordinates.dtype not in (torch.int32,torch.int64) or coordinates.device!=features.device:
        raise ValueError('integer coordinates on feature device required')
    b,z,y,x = coordinates.unbind(1)
    if torch.any(b<0) or torch.any(b>=batch_size) or torch.any(z!=0) or torch.any(y<0) or torch.any(y>=ny) or torch.any(x<0) or torch.any(x>=nx):
        raise ValueError('pillar outside scatter grid')
    indices = b*(ny*nx)+y*nx+x
    if len(torch.unique(indices))!=len(indices):
        raise ValueError('duplicate scatter cell')
    canvas = features.new_zeros((batch_size*ny*nx,features.shape[1]))
    canvas[indices] = features
    return canvas.reshape(batch_size,ny,nx,features.shape[1]).permute(0,3,1,2).contiguous()
