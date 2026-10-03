import unittest
import numpy as np
import torch
from pipeline.detector_loss import detector_loss
from cohort.sustained_loss import class_balanced_objective
from cohort.sustained_literal_loss import literal_losses,compare_losses

class LiteralLossTests(unittest.TestCase):
 def fixture(self,labels):
  rng=np.random.default_rng(17);n=len(labels);heads={'classification':rng.normal(size=(n,4)).astype(np.float32),'box_residuals':rng.normal(size=(n,7)).astype(np.float32),'direction':rng.normal(size=(n,2)).astype(np.float32)};truth={'labels':np.array(labels,dtype=np.int64),'box_targets':rng.normal(size=(n,7)).astype(np.float32),'direction_targets':rng.integers(0,2,size=n)};return heads,truth
 def test_reference_and_weighted_present_absent_empty_classes(self):
  for labels in [[1,1,2,3,4,0,-1],[1,3,3,0,-1],[0,0,-1]]:
   heads,truth=self.fixture(labels);out={k:torch.from_numpy(v)[None] for k,v in heads.items()};targets=tuple(torch.from_numpy(truth[k])[None] for k in ['labels','box_targets','direction_targets'])
   for balanced in [False,True]:
    found,parts=literal_losses(heads,truth,class_balanced=balanced);expected=class_balanced_objective(out,targets) if balanced else detector_loss(out['classification'],out['box_residuals'],out['direction'],*targets)
    compare_losses(found,{k:float(v) for k,v in expected.items()});self.assertAlmostEqual(sum(p['positive_focal']+p['negative_focal'] for p in parts.values()),found['classification']);self.assertEqual(sum(p['positive_anchors'] for p in parts.values()),sum(x>0 for x in labels))
 def test_reported_nan_missing_or_changed_losses_refused(self):
  heads,truth=self.fixture([1,2,3,4]);losses,_=literal_losses(heads,truth)
  for altered in [{**losses,'total':float('nan')},{k:v for k,v in losses.items() if k!='direction'},{**losses,'classification':losses['classification']+.1}]:
   with self.assertRaises(ValueError):compare_losses(losses,altered)
 def test_nonfinite_bad_shape_and_bad_integer_targets_refused(self):
  heads,truth=self.fixture([1,0,-1])
  for bad in [{**heads,'classification':np.full((3,4),np.nan)},{**heads,'direction':np.zeros((3,3))}]:
   with self.assertRaises(ValueError):literal_losses(bad,truth)
  for bad in [{**truth,'labels':np.array([5,0,-1])},{**truth,'direction_targets':np.array([2,0,0])},{**truth,'labels':truth['labels'].astype(float)}]:
   with self.assertRaises(ValueError):literal_losses(heads,bad)
if __name__=='__main__':unittest.main()
