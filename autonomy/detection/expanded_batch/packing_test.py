import unittest,numpy as np
from detection.expanded_batch.packing import pack_case,range_observations

class PackingContract(unittest.TestCase):
 def test_grid_boundaries_and_physical_source_lineage(self):
  points=np.array([[-64.,-64.,0.,1.],[63.999,63.999,0.,2.],[64.,0.,0.,3.],[0.,0.,6.,4.],[0.,0.,0.,5.]])
  for name,grid in [('grid_fine',1024),('grid_coarse',256)]:
   value=pack_case(points,name,seed=17,pillar_cap=20000);self.assertEqual(value['grid'],[grid,grid]);self.assertEqual(value['counts_report']['retained_points'],3)
   ids=value['source_indices'];np.testing.assert_array_equal(value['points'][ids>=0],points[ids[ids>=0]])
   self.assertEqual(value['coordinates'][0,2:].tolist(),[0,0]);self.assertEqual(value['coordinates'][-1,2:].tolist(),[grid-1,grid-1])
 def test_ragged_retains_dense_pillar_and_matches_uncapped_groups(self):
  points=np.array([[.01+i*.0001,.01,0.,float(i)] for i in range(70)]+[[1.,1.,0.,1.]])
  value=pack_case(points,'ragged_pillars',seed=17,pillar_cap=20000);self.assertEqual(value['points'].shape,(71,4));self.assertEqual(value['counts'].tolist(),[70,1]);self.assertEqual(value['counts_report']['point_limit_dropped_points'],0);np.testing.assert_array_equal(value['points'],points[value['source_indices']])
 def test_ragged_pillar_cap_is_separate_and_repeatable(self):
  points=np.array([[float(i),float(i),0.,float(i)] for i in range(30)])
  a=pack_case(points,'ragged_pillars',seed=9,pillar_cap=4);b=pack_case(points,'ragged_pillars',seed=9,pillar_cap=4);self.assertEqual(len(a['counts']),4);self.assertEqual(a['counts_report']['pillar_limit_dropped_points'],26);np.testing.assert_array_equal(a['source_indices'],b['source_indices'])
 def test_range_gather_preserves_laser_return_and_padding(self):
  grids={};identity=[];physical=[]
  for laser in range(1,6):
   for ret in (1,2):
    raw=np.zeros((2,3,4));raw[0,1]=[10.,laser+ret/10,2.,99.];grids[laser,ret]=raw;identity.append([laser,ret,0,1]);physical.append([0.,0.,0.,laser+ret/10])
  ids=np.array([[0,9,-1]]);value=range_observations(grids,np.array(physical),np.array(identity),ids);self.assertEqual(value['range_pixels'].tolist(),[[[0,0,1],[9,0,1],[-1,-1,-1]]]);self.assertEqual(value['range_raw_1_1'].shape,(1,3,2,3));self.assertNotIn('nlz',value);self.assertNotIn('labels',value)
  bad=np.array(identity);bad[0,3]=2
  with self.assertRaises(ValueError):range_observations(grids,np.array(physical),bad,ids)
 def test_range_identity_and_intensity_corruption_is_rejected(self):
  grids={(l,r):np.array([[[1.,2.,3.,0.]]]) for l in range(1,6) for r in (1,2)};identity=np.array([[l,r,0,0] for l in range(1,6) for r in (1,2)]);points=np.zeros((10,4));points[:,3]=2.
  bad=points.copy();bad[3,3]=7
  with self.assertRaises(ValueError):range_observations(grids,bad,identity,np.arange(10)[None])

if __name__ == "__main__":
 unittest.main()
