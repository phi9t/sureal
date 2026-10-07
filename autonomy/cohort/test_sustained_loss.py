import unittest,torch
from cohort.sustained_loss import class_balanced_objective
from detection.fixed_batch_models import objective

class SustainedLossTests(unittest.TestCase):
 def fixture(self,labels):
  torch.manual_seed(17);n=len(labels)
  outputs={'classification':torch.randn(1,n,4,requires_grad=True),'box_residuals':torch.randn(1,n,7,requires_grad=True),'direction':torch.randn(1,n,2,requires_grad=True)}
  targets=(torch.tensor([labels]),torch.zeros(1,n,7),torch.zeros(1,n,dtype=torch.long));return outputs,targets
 def test_matches_admitted_all_present_equation(self):
  outputs,targets=self.fixture([1,1,2,3,4,0,-1]);expected=objective(outputs,targets,{'loss':'class_balanced_positive'});found=class_balanced_objective(outputs,targets)
  for key in expected:torch.testing.assert_close(found[key],expected[key],rtol=0,atol=0)
 def test_absent_classes_match_literal_masked_sum(self):
  outputs,targets=self.fixture([1,1,3,0,-1]);found=class_balanced_objective(outputs,targets);logits=outputs['classification'][0];labels=targets[0][0];normalizer=3.;total=logits.sum()*0
  for i,label in enumerate(labels.tolist()):
   if label<0:continue
   for cls in range(1,5):
    p=logits[i,cls-1].sigmoid();positive=label==cls
    if positive:term=-.25*(1-p)**2*torch.log(p)*normalizer/(4*int((labels==cls).sum()))
    else:term=-.75*p**2*torch.log(1-p)
    total=total+term
  torch.testing.assert_close(found['classification'],total/normalizer,rtol=1e-6,atol=1e-6)
  found['total'].backward();self.assertTrue(all(x.grad is not None and torch.isfinite(x.grad).all() for x in outputs.values()))
 def test_no_positive_anchor_preserves_reference_negative_loss(self):
  outputs,targets=self.fixture([0,0,-1]);found=class_balanced_objective(outputs,targets);expected=objective(outputs,targets,{'loss':'reference'})
  for key in expected:torch.testing.assert_close(found[key],expected[key],rtol=0,atol=0)

if __name__=='__main__':unittest.main()
