import unittest
from cohort.sustained_scoring_budget import scoring_budget,stage_timeout
class NativeScoringBudgetTests(unittest.TestCase):
 def test_four_hour_native_limit_and_separate_host_grace(self):
  native,host=scoring_budget();self.assertEqual(native,4*60*60);self.assertEqual(host-native,300)
 def test_only_metric_stages_receive_four_hour_host_bound(self):
  self.assertEqual(stage_timeout(True),14700);self.assertEqual(stage_timeout(False),1800)
  with self.assertRaises(ValueError):stage_timeout(1)
 def test_limits_remain_bounded_and_integer(self):
  for value in [True,599,14401,1800.5,float('inf')]:
   with self.assertRaises(ValueError):scoring_budget(value)
  self.assertEqual(scoring_budget(600),(600,900))
if __name__=='__main__':unittest.main()
