import unittest
from training_execution.protocol import validate_cohort,quality_gate
class ProtocolTests(unittest.TestCase):
 def frames(self):return [{'identity':f's{i}:100','split':'training','positive_anchors':{str(k):1 for k in range(1,5)}} for i in range(16)]
 def test_full_class_training_fixture(self):self.assertEqual(validate_cohort(self.frames())['frames'],16)
 def test_missing_class_is_refused(self):
  frames=self.frames()
  for f in frames:f['positive_anchors']['4']=0
  with self.assertRaises(ValueError):validate_cohort(frames)
 def test_heldout_and_duplicate_refused(self):
  frames=self.frames();frames[0]['split']='validation'
  with self.assertRaises(ValueError):validate_cohort(frames)
  frames=self.frames();frames[1]=frames[0]
  with self.assertRaises(ValueError):validate_cohort(frames)
 def test_mean_cannot_hide_failed_class(self):self.assertFalse(quality_gate({'1':.99,'2':.99,'3':.79,'4':.99}))
 def test_absent_class_cannot_pass(self):self.assertFalse(quality_gate({'1':.99,'2':.99,'3':.99}))
 def test_all_classes_pass(self):self.assertTrue(quality_gate({str(i):.8 for i in range(1,5)}))
if __name__=='__main__':unittest.main()
