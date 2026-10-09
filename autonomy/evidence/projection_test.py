import unittest
from evidence.projection import project_experiments, quality
class ProjectionTests(unittest.TestCase):
 def run_case(self):
  point={'step':500,'LEVEL2_per_class':{str(i):{'AP':.9,'APH':.9} for i in range(1,5)},'all_class_quality_passed':True}
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
 def test_running_case_without_score_stays_running(self):
  definitions={'baseline':{'architecture':'baseline'}}
  result={'_run_metadata':{'matrix':definitions},'cases':{'baseline':{'status':'training in progress','curve':[{'step':500}]}}}
  row=project_experiments('run',definitions,result,'a',None,None)[0]
  self.assertEqual(row['stage'],'running_or_verifying')
  self.assertEqual(row['terminal_LEVEL2_per_class'],{})
  self.assertIsNone(row['worst_terminal_APH'])
 def test_malformed_running_score_record_is_refused(self):
  definitions={'baseline':{'architecture':'baseline'}}
  malformed={str(i):{'AP':.9,'APH':.9} for i in range(1,5)}
  del malformed['4']['AP']
  result={'_run_metadata':{'matrix':definitions},'cases':{'baseline':{'status':'training in progress','curve':[{'step':500,'LEVEL2_per_class':malformed}]}}}
  with self.assertRaises(ValueError):project_experiments('run',definitions,result,'a',None,None)
 def test_populated_class_score_record_uses_groundtruth_scope(self):
  definitions={'baseline':{'architecture':'baseline'}}
  point={'step':500,
         'groundtruth_by_class':{'1':3,'2':3,'3':11,'4':0},
         'LEVEL2_per_class':{'1':{'AP':.9,'APH':.8},'2':{'AP':.9,'APH':.7},'3':{'AP':.9,'APH':.6}}}
  result={'_run_metadata':{'matrix':definitions},'cases':{'baseline':{'status':'training in progress','curve':[point]}}}
  row=project_experiments('run',definitions,result,'a',None,None)[0]
  self.assertEqual(set(row['terminal_LEVEL2_per_class']),{'1','2','3'})
  self.assertEqual(row['worst_terminal_APH'],.6)
 def test_populated_class_score_record_displays_without_passing_quality(self):
  definitions={'baseline':{'architecture':'baseline'}}
  point={'step':500,
         'groundtruth_by_class':{'1':3,'2':3,'3':11,'4':0},
         'LEVEL2_per_class':{'1':{'AP':.9,'APH':.81},'2':{'AP':.9,'APH':.82},'3':{'AP':.9,'APH':.83}}}
  result={'_run_metadata':{'matrix':definitions},'cases':{'baseline':{'status':'training in progress','curve':[point]}}}
  row=project_experiments('run',definitions,result,'a',None,None)[0]
  self.assertEqual(set(row['terminal_LEVEL2_per_class']),{'1','2','3'})
  self.assertEqual(row['worst_terminal_APH'],.81)
  self.assertFalse(quality(point))
  overfit={'_run_metadata':{'matrix':definitions},'cases':{'baseline':{'status':'sustained native overfit','updates':750,'curve':[point,{**point,'step':750}]}}}
  with self.assertRaises(ValueError):project_experiments('run',definitions,overfit,'a',None,None)
 def test_three_class_score_record_without_class_source_is_refused(self):
  definitions={'baseline':{'architecture':'baseline'}}
  point={'step':500,'LEVEL2_per_class':{'1':{'AP':.9,'APH':.8},'2':{'AP':.9,'APH':.7},'3':{'AP':.9,'APH':.6}}}
  result={'_run_metadata':{'matrix':definitions},'cases':{'baseline':{'status':'training in progress','curve':[point]}}}
  with self.assertRaises(ValueError):project_experiments('run',definitions,result,'a',None,None)
 def test_all_class_quality_points_still_require_all_classes(self):
  definitions={'baseline':{'architecture':'baseline'}}
  point={'step':500,'all_class_quality_passed':False,'LEVEL2_per_class':{'1':{'AP':.9,'APH':.8},'2':{'AP':.9,'APH':.7},'3':{'AP':.9,'APH':.6}}}
  result={'_run_metadata':{'matrix':definitions},'cases':{'baseline':{'status':'training in progress','curve':[point]}}}
  with self.assertRaises(ValueError):project_experiments('run',definitions,result,'a',None,None)
 def test_registry_recipe_cannot_relabel_existing_evidence(self):
  result=self.run_case();closure={'candidate_sha256':'a','validation':{'all_cases_finished':True},'checks':[{'exit_code':0}]}
  with self.assertRaises(ValueError):project_experiments('run',{'baseline':{'architecture':'different','learning_rate':.1}},result,'a',closure,None)
if __name__=='__main__':unittest.main()
