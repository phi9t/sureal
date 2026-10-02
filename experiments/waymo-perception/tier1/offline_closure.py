import json,sys,unittest
from pathlib import Path
from tier1.verify_results import verify
sys.path.insert(0,'/experiment/tier1');test=unittest.TextTestRunner().run(unittest.defaultTestLoader.discover('/experiment/tier1',pattern='test_*.py'));assert test.wasSuccessful();result=verify('/tmp/candidate.json');result['live_cpu_contract_tests']=test.testsRun;Path('/outputs/check.json').write_text(json.dumps(result,indent=2));print('PASS offline release-aware closure',len(result['rows']),result['verified_stage_receipts'])
