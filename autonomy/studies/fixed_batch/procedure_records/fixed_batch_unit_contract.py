import json,sys,unittest
from pathlib import Path
sys.path.insert(0,'/experiment/tier1');r=unittest.TextTestRunner().run(unittest.defaultTestLoader.discover('/experiment/tier1',pattern='test_*.py'));assert r.wasSuccessful();Path('/outputs/check.json').write_text(json.dumps({'tests':r.testsRun,'failures':0,'live_cpu_contracts':True}))
