import tempfile,unittest
from pathlib import Path
from resources import scientific_budget
from resources.scientific_budget import reserve_write,fit_interval
class AdmissionTests(unittest.TestCase):
 def test_scientific_working_cap_is_20_gib_and_rejects_boundary(self):
  cap=20*1024**3
  self.assertEqual(getattr(scientific_budget,'SCIENTIFIC_WORKING_CAP_BYTES',None),cap)
  with tempfile.TemporaryDirectory() as d:
   self.assertEqual(reserve_write(d,cap-1)['limit'],cap)
   with self.assertRaises(ValueError):reserve_write(d,cap)
 def test_refuse_before_write(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'existing';p.write_bytes(b'x'*90)
   with self.assertRaises(ValueError):reserve_write(d,11,100)
   self.assertEqual(p.read_bytes(),b'x'*90);self.assertEqual(len(list(Path(d).iterdir())),1)
 def test_sustained_fit_after_regression(self):
  curve=[{'step':i,'cumulative_train_seconds':i/2,'all_class_quality_passed':ok} for i,ok in [(0,False),(25,True),(50,False),(100,True),(200,True)]]
  r=fit_interval(curve);self.assertEqual(r['first_stable_fit_update_interval'],[50,100]);self.assertEqual(r['confirmation_update'],200)
 def test_censored(self):
  r=fit_interval([{'step':0,'cumulative_train_seconds':0,'all_class_quality_passed':False},{'step':10000,'cumulative_train_seconds':500,'all_class_quality_passed':False}]);self.assertTrue(r['right_censored']);self.assertEqual(r['observed_updates'],10000)

if __name__ == "__main__":
 unittest.main()
