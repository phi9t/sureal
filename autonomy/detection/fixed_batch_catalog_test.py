import unittest
from detection.fixed_batch_catalog import catalog,select_fixture
class CatalogTests(unittest.TestCase):
 def test_one_axis_controls(self):
  cases=catalog();base=cases['baseline'];self.assertEqual(len(cases),16)
  for name,row in cases.items():
   changed=[k for k in base if row[k]!=base[k]]
   self.assertLessEqual(len(changed),1,name)
 def test_fixture_cannot_lack_a_class(self):
  bad={'identity':'s:1','uncovered_GT':0,'eligible_GT':5,'covered_objects':{'1':['a'],'2':['b'],'3':[],'4':['x']*5}}
  with self.assertRaises(ValueError):select_fixture({'validation':[bad]})
 def test_fixture_uses_coverage_then_size(self):
  def row(name,n,uncovered):return {'identity':name,'eligible_GT':n,'uncovered_GT':uncovered,'covered_objects':{str(c):list('abcde') for c in range(1,5)}}
  self.assertEqual(select_fixture({'validation':[row('b',20,0),row('a',19,1),row('c',15,0)]})['identity'],'c')

if __name__ == "__main__":
 unittest.main()
