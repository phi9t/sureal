"""Strictly close a matched study only after every native audit is admitted."""
import hashlib,json
from pathlib import Path
from admissions import required_fit_admissions
from balanced_gate import validate_balanced_fixture
from protocol import quality_gate
P=Path(__file__).resolve().parents[1];C=Path.home()/'.cache/waystone/waymo-perception';ids={'baseline':'balanced20261002a','residual_bev':'balanced20261002b'};sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();selection=json.loads((P/'research/balanced16-selection.candidate.json').read_text());audit=json.loads((P/'research/balanced16-labels-and-anchor-coverage-v3-verified.json').read_text());linkpath=P/'research/balanced16-fixture-link-verified.json';link=json.loads(linkpath.read_text());results={};manifests={}
assert link['validation']['identical_inputs_and_recipe']
for p,h in link['source_pins'].items():assert sha(p)==h
for p,h in link['parents'].items():assert sha(p)==h
for p,h in link['upstream_receipts'].items():assert sha(p)==h
for variant,rid in ids.items():
 run=C/'insula'/f'cohort16-{variant}-{rid}';meta=json.loads((run/'run.json').read_text());manifests[variant]=meta['manifest'];validate_balanced_fixture(meta['manifest']['frames'],selection,audit);admissions=required_fit_admissions(run)
 for p,h in meta['source_sha256'].items():assert sha(run/'source'/p)==h
 quality=P/'research'/f'cohort16-{variant}-{rid}-quality-parallel-v3.json';q=json.loads(quality.read_text());grid=meta['manifest']['execution']['checkpoint_grid'];assert [r['step'] for r in q['curve']]==grid
 expected={f'{name}-{step}' for step in grid for name in ('prepare','score','proposal-audit','export-metric-audit')};assert {c['name'] for c in q['checks']}==expected and len(q['checks'])==len(expected) and all(c['exit_code']==0 for c in q['checks'])
 for p,h in q['artifacts'].items():assert sha(p)==h
 for p,h in q['worker_hashes'].items():assert sha(p)==h
 for row in q['curve']:assert row['all_class_quality_passed']==quality_gate({k:v['APH'] for k,v in row['LEVEL2_per_class'].items()})
 train=admissions['train']['validation'];accepted=all(row['all_class_quality_passed'] for row in q['curve'][-2:]) and train['loss_gate_passed'];assert q['full_class_fit_passed']==accepted
 results[variant]={'run_id':rid,'native_curve':q['curve'],'full_class_fit_passed':accepted,'parameters':train['parameters'],'initial_mean_loss':train['initial_mean_loss'],'final_mean_loss':train['final_mean_loss'],'cumulative_train_seconds':train['cumulative_train_seconds'],'native_scoring_and_audits_seconds':q['native_scoring_and_audits_seconds'],'quality_receipt':str(quality),'quality_sha256':sha(quality),'required_admissions':admissions,'peak_allocated_bytes':train['peak_allocated_bytes'],'peak_rss_kib':train['peak_rss_kib']}
a,b=manifests.values();assert a['frames']==b['frames'] and a['execution']==b['execution'];result={'stage':'completed','run_ids':ids,'results':results,'matched_inputs_and_recipe':True,'strict_fixture_link_sha256':sha(linkpath),'full_dataset_readiness':any(r['full_class_fit_passed'] for r in results.values()),'scope':'balanced16 training-only fitting comparison; negative result blocks larger-training promotion and does not close the research program'};(P/'research/balanced-study-recovery-20261002.json').write_text(json.dumps(result,indent=2));print('COMPLETE matched study; full-dataset fitting gate:',result['full_dataset_readiness'])
