import unittest
from evidence.projection import project_experiments
class ProjectionTests(unittest.TestCase):
 def run_case(self):
  point={'step':500,'LEVEL2_per_class':{str(i):{'APH':.9} for i in range(1,5)},'all_class_quality_passed':True}
  return {'_run_metadata':{'matrix':{'baseline':{'architecture':'baseline'}}},'finished':True,'cases':{'baseline':{'status':'sustained native overfit','updates':750,'curve':[point,{**point,'step':750}]}}}
 def test_native_fit_requires_matching_final_closure(self):
  result=self.run_case();definitions={'baseline':{'architecture':'baseline'}}
  row=project_experiments('run',definitions,result,'a'*64,None,None)[0];self.assertEqual(row['stage'],'native_fit_pending_closure')
  closure={'candidate_sha256':'a'*64,'validation':{'all_cases_finished':True},'checks':[{'exit_code':0}]}
  self.assertEqual(project_experiments('run',definitions,result,'a'*64,closure,None)[0]['stage'],'verified_overfit')
  closure['candidate_sha256']='b'*64
  with self.assertRaises(ValueError):project_experiments('run',definitions,result,'a'*64,closure,None)
 def test_admission_and_equivalence_are_not_trained_results(self):
  definitions={'point_attention':{'architecture':'point_attention'}};admission={'cases':{'point_attention':{'validation':{'case':definitions['point_attention'],'exact_repeated_three_update_model_adam_rng':True}}}}
  row=project_experiments('run',definitions,None,None,None,admission)[0];self.assertEqual(row['stage'],'gpu_admitted');self.assertFalse(row['trained'])
  result={'_run_metadata':{'matrix':definitions},'cases':{'point_attention':{'status':'exact observation equivalence control'}}}
  self.assertFalse(project_experiments('run',definitions,result,'a',None,admission)[0]['trained'])
 def test_loss_reduction_cannot_promote_invalid_native_pass(self):
  result=self.run_case();result['cases']['baseline']['curve'][-1]['LEVEL2_per_class']['4']['APH']=.2
  with self.assertRaises(ValueError):project_experiments('run',{'baseline':{'architecture':'baseline'}},result,'a',None,None)
 def test_registry_recipe_cannot_relabel_existing_evidence(self):
  result=self.run_case();closure={'candidate_sha256':'a','validation':{'all_cases_finished':True},'checks':[{'exit_code':0}]}
  with self.assertRaises(ValueError):project_experiments('run',{'baseline':{'architecture':'different','learning_rate':.1}},result,'a',closure,None)
if __name__=='__main__':unittest.main()
