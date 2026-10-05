"""Native PointPillars adaptation with source-style dense anchor head.

Flatten order is row(y), column(x), anchor; metric anchor generation is external.
No labels, ground-truth IDs, NLZ indicators or box metadata are model inputs.
"""
import torch
from torch import nn
from pipeline.pillar_encoder import PillarFeatureNet,decorate,scatter


def norm(channels):
    return nn.BatchNorm2d(channels,eps=1e-3,momentum=.01)


class PillarDetector(nn.Module):
    def __init__(self,*,nx,ny,classes,anchors_per_cell,cell_size,origin):
        super().__init__()
        if any(type(v) is not int or v<=0 for v in (nx,ny,classes,anchors_per_cell)) or nx%8 or ny%8:
            raise ValueError('positive grid divisible by eight and head counts required')
        self.nx,self.ny,self.classes,self.anchors_per_cell=nx,ny,classes,anchors_per_cell
        self.cell_size,self.origin=cell_size,origin
        self.encoder=PillarFeatureNet()
        self.blocks=nn.ModuleList();self.upsample=nn.ModuleList()
        previous=64
        for channels,extra_layers,upstride in [(64,3,1),(128,5,2),(256,5,4)]:
            layers=[nn.ZeroPad2d(1),nn.Conv2d(previous,channels,3,stride=2,bias=False),norm(channels),nn.ReLU()]
            for _ in range(extra_layers):
                layers.extend([nn.Conv2d(channels,channels,3,padding=1,bias=False),norm(channels),nn.ReLU()])
            self.blocks.append(nn.Sequential(*layers))
            self.upsample.append(nn.Sequential(nn.ConvTranspose2d(channels,128,upstride,stride=upstride,bias=False),norm(128),nn.ReLU()))
            previous=channels
        self.class_head=nn.Conv2d(384,anchors_per_cell*classes,1)
        self.box_head=nn.Conv2d(384,anchors_per_cell*7,1)
        self.direction_head=nn.Conv2d(384,anchors_per_cell*2,1)

    def forward(self,points,counts,coordinates,*,batch_size):
        decorated=decorate(points,counts,coordinates,cell_size=self.cell_size,origin=self.origin)
        image=scatter(self.encoder(decorated),coordinates,batch_size=batch_size,nx=self.nx,ny=self.ny)
        parts=[]
        for block,up in zip(self.blocks,self.upsample):
            image=block(image);parts.append(up(image))
        features=torch.cat(parts,dim=1)
        def flatten(head,width):
            value=head(features).permute(0,2,3,1).contiguous()
            return value.reshape(batch_size,-1,width)
        return {'classification':flatten(self.class_head,self.classes),
                'box_residuals':flatten(self.box_head,7),
                'direction':flatten(self.direction_head,2)}
