"""Bind each run to the independently covered balanced selection."""
from admissions import validate_coverage_claim

def validate_balanced_fixture(frames,selection,audit):
 identities=[f['identity'] for f in frames];selected=[f['identity'] for f in selection['frames']];audited={f['identity']:f for f in audit['validation']}
 if len(identities)!=16 or len(set(identities))!=16 or len(selected)!=16 or set(identities)!=set(selected) or set(identities)!=set(audited):raise ValueError('Run is not the independently audited balanced selection')
 if not audit['label_and_anchor_coverage_gate_passed']:raise ValueError('Independent coverage admission missing')
 for f in frames:
  row=audited[f['identity']]
  if not row['all_anchor_labels_indices_residuals_directions_exact'] or f['positive_anchors']!=row['positive_anchor_counts_by_class']:raise ValueError('Run anchor coverage is not linked to independent audit')
 summary=validate_coverage_claim(audit['positive_anchor_covered_object_coverage'],audit['validation'])
 return {'frames':16,'exact_selection_and_independent_coverage_link':True,'covered_coverage':summary}

if __name__=='__main__':
 import json
 from pathlib import Path
 p=json.loads(Path('/tmp/input/payload.json').read_text());result={variant:validate_balanced_fixture(manifest['frames'],p['selection'],p['audit']) for variant,manifest in p['manifests'].items()};a,b=p['manifests'].values();assert a['frames']==b['frames'] and a['execution']==b['execution'];Path('/outputs/check.json').write_text(json.dumps({'candidates':result,'identical_inputs_and_recipe':True},indent=2));print('PASS strict balanced fixture link')
