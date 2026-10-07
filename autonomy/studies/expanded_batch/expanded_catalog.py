"""Frozen planned-idea recipes and explicit mechanism controls."""
from detection.fixed_batch_catalog import BASE

def catalog():
 names=['grid_fine','grid_coarse','ragged_pillars','point_attention','point_mlp_control','range_fusion','zero_range_control','sparse_bev_transformer']
 return {name:{**BASE,'architecture':name,'observation':name if name in ['grid_fine','grid_coarse','ragged_pillars'] else 'range_fusion' if name in ['range_fusion','zero_range_control'] else 'baseline'} for name in names}
