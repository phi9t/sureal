import json
from pathlib import Path
import torch
from pipeline.pillar_detector import PillarDetector
from gpu.norm_variants import configure_norm
from gpu.architecture_variants import configure_architecture
from gpu.architecture_weight_contract import verify_shared_weights

def make():
 torch.manual_seed(17)
 return configure_norm(PillarDetector(nx=8,ny=8,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-1.,-1.)),'gn_backbone')
for variant in ['deep_pfn','context_pfn','residual_bev']:verify_shared_weights(make(),configure_architecture(make(),variant))
bad=configure_architecture(make(),'residual_bev')
with torch.no_grad():bad.blocks[0][4].unit[0].weight.add_(1)
try:verify_shared_weights(make(),bad)
except AssertionError:pass
else:raise AssertionError('corrupt wrapped residual tensor escaped shared-weight gate')
Path('/outputs/check.json').write_text(json.dumps({'all_baseline_tensors_checked':True,'deliberately_corrupted_residual_branch_rejected':True}));print('PASS complete shared-weight coverage and corruption rejection')
