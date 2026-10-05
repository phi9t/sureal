"""Live terminal all-pillar cap control; identical heads preserve native scores."""
import hashlib,json
from pathlib import Path
import numpy as np
import torch
from tier1.models import build,deterministic
job=json.loads(Path('/tmp/inputs/job.json').read_text());deterministic();saved=torch.load('/tmp/retained/checkpoint.pt',map_location='cuda',weights_only=False);model=build(job['case']).cuda();model.eval()
with np.load('/tmp/fixture/observations.npz') as a:first=[torch.from_numpy(a[k]).cuda() for k in ['points','counts','coordinates']]
with np.load('/tmp/allpillars/observations.npz') as a:second=[torch.from_numpy(a[k]).cuda() for k in ['points','counts','coordinates']]
assert all(torch.equal(a,b) for a,b in zip(first,second));first[0]=first[0].float();second[0]=second[0].float()
with torch.no_grad():
 initial_a=model(*first,batch_size=1);initial_b=model(*second,batch_size=1);assert all(torch.equal(initial_a[k],initial_b[k]) for k in initial_a)
 with np.load('/tmp/initial/heads-00.npz') as expected:
  for k in initial_a:np.testing.assert_array_equal(initial_a[k][0].cpu().numpy(),expected[k])
 model.load_state_dict(saved['model'])
 a=model(*first,batch_size=1);b=model(*second,batch_size=1)
 assert all(torch.equal(a[k],b[k]) for k in a)
 with np.load('/tmp/terminal/heads-00.npz') as expected:
  for k in a:np.testing.assert_array_equal(a[k][0].cpu().numpy(),expected[k])
score=json.loads(Path('/tmp/score/check.json').read_text());report={'all_pillars_initial_and_terminal_inputs_exact':True,'initial_full_heads_exact_on_GPU':True,'terminal_full_heads_exact_to_baseline_producer':True,'inherited_native_LEVEL2_per_class':score['LEVEL2_per_class'],'native_equivalence_reason':'identical heads plus same physical measurements/nativeGT and deterministic audited decoder; no training effect because cap does not bind','scope':'no-effect cap control, not an independently trained variant'};Path('/outputs/check.json').write_text(json.dumps(report,indent=2));print('PASS terminal all-pillar inference and native-score equivalence')
