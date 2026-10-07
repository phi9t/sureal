import unittest,torch
from detection.expanded_batch.catalog import catalog
from detection.expanded_batch.models import build,bind_observations
from detection.fixed_batch_models import build as baseline_build
from detection.fixed_batch_catalog import BASE
from detection.pillar_encoder import decorate

class FactoryContract(unittest.TestCase):
 def setUp(self):torch.manual_seed(17);torch.set_num_threads(2)
 def test_matrix_has_six_ideas_and_explicit_controls(self):
  self.assertEqual(set(catalog()),{'grid_fine','grid_coarse','ragged_pillars','point_attention','point_mlp_control','range_fusion','zero_range_control','sparse_bev_transformer'})
 def test_grid_strides_and_shared_initial_weights(self):
  torch.manual_seed(17);reference=baseline_build(BASE)
  for name,size,cell,stride in [('grid_fine',1024,.125,4),('grid_coarse',256,.5,1)]:
   torch.manual_seed(17);model=build(catalog()[name]);self.assertEqual((model.nx,model.ny),(size,size));self.assertEqual(model.cell_size,(cell,cell));self.assertEqual(model.blocks[0][1].stride,(stride,stride))
   for key,value in reference.state_dict().items():torch.testing.assert_close(model.state_dict()[key],value,rtol=0,atol=0)
 def test_compatible_heads_and_upsample_initial_weights(self):
  torch.manual_seed(17);reference=baseline_build(BASE)
  for name in ['ragged_pillars','point_attention','point_mlp_control','sparse_bev_transformer','range_fusion','zero_range_control']:
   torch.manual_seed(17);model=build(catalog()[name])
   for prefix in ['class_head','box_head','direction_head','upsample']:
    original=getattr(reference,prefix).state_dict();candidate=getattr(model,prefix).state_dict()
    for key,value in original.items():torch.testing.assert_close(candidate[key],value,rtol=0,atol=0)
 def test_ragged_and_sparse_factories_produce_pillar_features(self):
  points=torch.rand(6,4);counts=torch.tensor([3,3]);coords=torch.tensor([[0,0,255,255],[0,0,256,256]]);model=build(catalog()['ragged_pillars']).eval();decorated=model.decorate_points(points,counts,coords);self.assertEqual(model.encoder(decorated,counts).shape,(2,64))
  model=build(catalog()['sparse_bev_transformer']).eval();images=model.spatial(torch.rand(2,64),coords,batch_size=1);self.assertEqual([tuple(x.shape) for x in images],[(1,64,256,256),(1,128,128,128),(1,256,64,64)])
