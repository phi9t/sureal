"""Read-only live closure of all extended contracts and complete native matrix."""
import json,sys,unittest
from pathlib import Path
from advanced.verify_results import verify
sys.path.insert(0,'/experiment/advanced')
tests=unittest.TextTestRunner().run(unittest.defaultTestLoader.discover('/experiment/advanced',pattern='test_*.py'))
assert tests.wasSuccessful()
result=verify('/tmp/candidate.json');assert result['all_cases_finished'] and len(result['rows'])==8
result['live_cpu_contract_tests']=tests.testsRun
Path('/outputs/check.json').write_text(json.dumps(result,indent=2))
print('PASS live expanded closure',len(result['rows']),result['verified_stage_receipts'],flush=True)
