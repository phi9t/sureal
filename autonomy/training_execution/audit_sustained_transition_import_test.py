import builtins,contextlib,importlib.util,os,runpy,sys,tempfile,textwrap,types,unittest
from pathlib import Path
from unittest.mock import patch


class StopAfterReferenceImport(RuntimeError):pass


def module(name,**attrs):
 m=types.ModuleType(name)
 for key,value in attrs.items():setattr(m,key,value)
 return m


@contextlib.contextmanager
def replaced_modules(values):
 missing=object();old={name:sys.modules.get(name,missing) for name in values}
 sys.modules.update(values)
 try:yield
 finally:
  for name,value in old.items():
   if value is missing:sys.modules.pop(name,None)
   else:sys.modules[name]=value


@contextlib.contextmanager
def different_cwd_and_sys_path(cwd,paths):
 old_cwd=Path.cwd();old_path=sys.path[:]
 os.chdir(cwd);sys.path[:]=[str(path) for path in paths]+old_path
 try:yield
 finally:
  sys.path[:]=old_path;os.chdir(old_cwd)


def stub_runtime_modules():
 cuda=module('torch.cuda',is_available=lambda:True,device_count=lambda:1,reset_peak_memory_stats=lambda:(_ for _ in ()).throw(StopAfterReferenceImport()))
 return {
  'torch':module('torch',cuda=cuda),
  'training_execution.sustained_sources':module('training_execution.sustained_sources',validate_sources=lambda *a,**k:None),
  'detection.sustained_contract':module('detection.sustained_contract',validate_contract=lambda *a,**k:None),
  'resources.replay_values':module('resources.replay_values',require_exact_state=lambda *a,**k:None),
  'detection.sustained_loss':module('detection.sustained_loss',class_balanced_objective=lambda *a,**k:None),
  'detection.detector_recipe_catalog':module('detection.detector_recipe_catalog',catalog=lambda:{}),
  'detection.detector_recipe_models':module('detection.detector_recipe_models',build=lambda case:None,optimizer=lambda model,case:None,deterministic=lambda:None,objective=lambda output,truth,case:None),
  'training_execution.replay_sustained':module('training_execution.replay_sustained',main=lambda:None),
 }


def run_verifier_until_after_reference_import(worker,cwd,sys_path):
 real_find_spec=importlib.util.find_spec
 def find_spec(name,*args,**kwargs):
  if name=='tensorflow':return None
  return real_find_spec(name,*args,**kwargs)
 with replaced_modules(stub_runtime_modules()),different_cwd_and_sys_path(cwd,sys_path),patch('importlib.util.find_spec',side_effect=find_spec):
  runpy.run_path(str(worker),run_name='__main__')


class TransitionVerifierImportTests(unittest.TestCase):
 def test_runpy_verifier_loads_sibling_reference_from_verifier_directory(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);verifier=root/'verifier';verifier.mkdir();foreign=root/'experiment';foreign.mkdir();cwd=root/'cwd';cwd.mkdir()
   (verifier/'audit_sustained_transition.py').write_bytes(Path(__file__).with_name('audit_sustained_transition.py').read_bytes())
   (verifier/'sustained_chunk_reference.py').write_text(textwrap.dedent("""
   import builtins
   builtins.sustained_reference_source='verifier'
   def reference_chunk(*args,**kwargs):
    return 'verifier'
   """))
   (foreign/'sustained_chunk_reference.py').write_text("raise AssertionError('foreign sustained_chunk_reference loaded')\n")
   package=foreign/'training_execution';package.mkdir();(package/'__init__.py').write_text('')
   (package/'sustained_chunk_reference.py').write_text("raise AssertionError('package sustained_chunk_reference loaded')\n")
   with self.assertRaises(StopAfterReferenceImport):
    run_verifier_until_after_reference_import(verifier/'audit_sustained_transition.py',cwd,[foreign])
   self.assertEqual(builtins.sustained_reference_source,'verifier')
   del builtins.sustained_reference_source

 def test_runpy_verifier_requires_missing_sibling_reference_file(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);verifier=root/'verifier';verifier.mkdir();cwd=root/'cwd';cwd.mkdir()
   (verifier/'audit_sustained_transition.py').write_bytes(Path(__file__).with_name('audit_sustained_transition.py').read_bytes())
   with self.assertRaisesRegex(ValueError,'regular non-symlinked file required'):
    run_verifier_until_after_reference_import(verifier/'audit_sustained_transition.py',cwd,[])


if __name__=='__main__':unittest.main()
