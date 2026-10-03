import unittest,runpy,json,csv,pathlib,copy
module=runpy.run_path('/experiment/check.py');verify,aggregate=module['verify'],module['aggregate'];score=json.loads(pathlib.Path('/source/pooled-0-0.json').read_text());refs=[list(csv.DictReader((pathlib.Path('/source')/f'{s}-expected-0.tsv').open(),delimiter='\t')) for s in ['training','validation']];expected=aggregate(refs)
class FinitePooledContract(unittest.TestCase):
 def test_nonfinite_observed_displacement_refuses(self):
  for key in ['minAde','minFde']:
   for value in [float('nan'),float('inf'),-float('inf'),'NaN','Infinity']:
    with self.subTest(key=key,value=str(value)):
     bad=copy.deepcopy(score);bad['metrics']['metricsBundles'][0][key]=value
     with self.assertRaises(ValueError):verify(bad,expected)
 def test_nonfinite_reference_displacement_refuses(self):
  for key in ['ade_sum','fde_sum']:
   for value in [float('nan'),float('inf'),-float('inf')]:
    with self.subTest(key=key,value=str(value)):
     bad=copy.deepcopy(expected);bad[1][key]=value
     with self.assertRaises(ValueError):verify(score,bad)
if __name__=='__main__':unittest.main()
