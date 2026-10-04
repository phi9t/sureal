import unittest
from pipeline.cohort_selection import select_cohorts

class CohortTests(unittest.TestCase):
    def test_order_independent_whole_segments(self):
        result=select_cohorts(['a','b','c','d'],['v1','v2','v3'],excluded={'v2'},train_count=2,dev_count=1,validation_count=1)
        other=select_cohorts(['d','c','b','a'],['v3','v2','v1'],excluded={'v2'},train_count=2,dev_count=1,validation_count=1)
        self.assertEqual(result,other)
        self.assertFalse(set(result['train'])&set(result['development']))
        self.assertNotIn('v2',result['validation'])

    def test_overlap_duplicate_and_insufficient_fail(self):
        for train,val in [(['a','a'],['b']),(['a'],['a']),(['a'],['b'])]:
            with self.assertRaises(ValueError):select_cohorts(train,val,excluded=set(),train_count=2,dev_count=1,validation_count=1)
