"""Recompute a descriptive analysis of existing admitted runs; never train a model.

Run: uv run --no-project --with matplotlib==3.10.0 python <this-file>
The output is a host analysis, not a new live Insula implementation receipt.
"""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
STEM = '2026-10-03-initial-experiments-analysis'
PINS = {}


def read(name):
    payload = (HERE / name).read_bytes()
    PINS[name] = hashlib.sha256(payload).hexdigest()
    return json.loads(payload)


def at(case, step):
    return next(row for row in case['curve'] if row['step'] == step)


def aph(row):
    classes = row['LEVEL2_per_class']
    assert set(classes) == {'1', '2', '3', '4'}
    result = [classes[str(c)]['APH'] for c in range(1, 5)]
    assert all(math.isfinite(x) and 0 <= x <= 1 for x in result)
    return result


def summarize(results, closure):
    assert results['finished'] and closure['validation']['all_cases_finished']
    admitted = {row['case']: row for row in closure['validation']['rows']}
    trained = {name for name, case in results['cases'].items() if case.get('curve')}
    assert set(admitted) == trained
    rows = {}
    for name, case in results['cases'].items():
        if not case.get('curve'):
            assert name == 'all_pillars'
            assert case['same_as'] == 'baseline' and case['native_quality_curve_inherited']
            read('tier1-terminal-cap-equivalence-verified.json')
            assert PINS['tier1-terminal-cap-equivalence-verified.json'] == case['terminal_GPU_equivalence_receipt_sha256']
            rows[name] = {'status': case['status'], 'kind': 'equivalence control'}
            continue
        terminal = case['curve'][-1]
        confirmed = case['time_to_fit'].get('confirmation_update')
        assert terminal['step'] == case['updates']
        for key in ('parameters', 'updates', 'time_to_fit', 'clipped_steps'):
            assert case[key] == admitted[name][key], (name, key)
        assert terminal['LEVEL2_per_class'] == admitted[name]['terminal_LEVEL2_per_class']
        assert case['status'] == admitted[name]['status']
        rows[name] = {
            'parameters': case['parameters'],
            'retained_terminal_update': case['updates'],
            'confirmation_update': confirmed,
            'first_fit_interval': case['time_to_fit'].get('first_stable_fit_update_interval'),
            'right_censored': case['time_to_fit']['right_censored'],
            'terminal_APH': aph(terminal),
            'confirmation_APH': aph(at(case, confirmed)) if confirmed is not None else None,
            'clipped_updates': case['clipped_steps'],
            'clipped_fraction_to_retained_terminal': case['clipped_steps'] / case['updates'],
            'confirmation_train_seconds': case['time_to_fit'].get('confirmation_train_seconds'),
            'timing_scope': 'synchronized training wall; contention prevents throughput ranking',
        }
    return rows


tier = read('tier1-overfit20261002b-results.json')
expanded = read('advanced-expanded20261002a-results.json')
tier_rows = summarize(tier, read('tier1-closure-live-final-v4-verified.json'))
expanded_rows = summarize(expanded, read('advanced-closure-expanded20261002a-verified.json'))
balanced = read('balanced-study-recovery-20261002.json')
native_v3 = read('balanced16-historical-v3-fullgt-metrics-verified.json')
read('balanced16-historical-v3-native-metric-audit-verified.json')
read('balanced16-historical-v3-proposal-audit-verified.json')
bn_counterfactual = read('one-batch-bn-counterfactual-verified.json')['validation']
bn_quality = read('one-batch-bn-counterfactual-scoring-verified.json')['validation']
old_norm = read('normalization-ablation-result.json')
read('architecture-first-cohort-results.json')
read('tier1-allclass-fixture-verified.json')
read('balanced16-coverage-oracle-native-verified.json')
read('balanced16-coverage-causes-verified.json')
read('sparse-head-support-live-verified.json')
read('tier1-heading-step2000a-verified.json')

balanced_rows = {}
for name, result in balanced['results'].items():
    producer = result['required_admissions']['train']['validation']
    visits = Counter(row['frame_index'] for row in producer['step_records'])
    assert visits == Counter({i: 125 for i in range(16)})
    components = producer['component_curve']
    assert len(components) == 48
    first, last = components[:16], components[-16:]
    mean = lambda values, key: sum(row[key] for row in values) / len(values)
    evaluation = sum(row['evaluation_losses']['total'] for row in last) / 16
    batch_statistics = sum(row['batch_statistics_losses']['total'] for row in last) / 16
    balanced_rows[name] = {
        'frame_visits': dict(sorted(visits.items())),
        'initial_negative_focal': mean(first, 'negative_focal'),
        'final_negative_focal': mean(last, 'negative_focal'),
        'initial_positive_anchor_focal': mean(first, 'positive_focal'),
        'final_positive_anchor_focal': mean(last, 'positive_focal'),
        'terminal_eval_loss': evaluation,
        'terminal_batch_statistics_loss': batch_statistics,
        'terminal_eval_to_batch_statistics_loss_ratio': evaluation / batch_statistics,
        'clipped_updates': producer['clipped_steps'],
        'historical_V2_ROI_APH': result['native_curve'][-1]['LEVEL2_per_class'],
    }

baseline = tier['cases']['baseline']
control = tier['cases']['no_clip']
assert at(baseline, 0)['head_sha256'] == at(control, 0)['head_sha256']
initial = at(control, 0)
counts = [initial['class_statistics'][str(c)]['positive_anchors'] for c in range(1, 5)]
total = sum(counts)
weights = [total / (4 * count) for count in counts]
derived = {
    'scope': 'descriptive reanalysis of existing verified experiments; no new training or native replay',
    'source_sha256': PINS,
    'analysis_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'plotting_library_version': matplotlib.__version__,
    'tier1': tier_rows,
    'expanded': expanded_rows,
    'balanced16_historical': balanced_rows,
    'balanced16_baseline2000_V3_fullnativeGT_APH': native_v3['validation']['LEVEL2_per_class'],
    'initial_allclass_positive_anchors': counts,
    'initial_positive_anchor_class_fractions': [count / total for count in counts],
    'positive_class_focal_reweighting': weights,
    'initial_background_to_positive_anchor_focal_ratio': initial['negative_focal'] / initial['positive_focal'],
    'additional_deep_PFN_parameter_fraction': (tier_rows['deep_pfn']['parameters'] - tier_rows['baseline']['parameters']) / tier_rows['baseline']['parameters'],
    'old17GT_frozen_BN_counterfactual': {
        'optimizer_updates': bn_counterfactual['optimizer_updates'],
        'weights_bitwise_unchanged': bn_counterfactual['weights_bitwise_unchanged'],
        'loss_before': bn_counterfactual['before_losses']['total'],
        'loss_after': bn_counterfactual['after_losses']['total'],
        'historical_mean_APH_before': old_norm['results'][0]['final']['mean_populated_class_APH'],
        'historical_mean_APH_after': bn_quality['mean_populated_class_APH'],
    },
    'exposure_normalization': {'historical16_frame_updates': 2000, 'visits_per_frame': 125, 'single_frame_first_native_pass': 500, 'single_frame_confirmation': 750, 'sixteen_frame_equal_visit_budgets': [8000, 12000], 'qualification': 'visit accounting, not a predicted fit time; frame mixture and sampler also differ'},
}
(HERE / (STEM + '.json')).write_text(json.dumps(derived, indent=2) + '\n')

plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'svg.fonttype': 'none', 'svg.hashsalt': STEM})
fig, axes = plt.subplots(2, 2, figsize=(14, 9.3), constrained_layout=True)
ax = axes[0, 0]
curves = [('GN backbone', baseline, '#245eaa'), ('Full BN', tier['cases']['full_bn'], '#bd6c0a'), ('No norm', tier['cases']['no_norm'], '#8c4a92'), ('Sparse transformer', expanded['cases']['sparse_bev_transformer'], '#b44545')]
for label, case, color in curves:
    rows = [row for row in case['curve'] if row['step'] > 0]
    ax.plot([row['step'] for row in rows], [min(aph(row)) for row in rows], 'o-', label=label, color=color, markersize=3)
ax.axhline(.8, color='gray', linestyle='--', linewidth=1)
ax.set(xscale='log', xlabel='Optimizer updates on one fixed frame', ylabel='Worst of four classes: native LEVEL2 APH', ylim=(0, 1.04), title='A. Gate separates optimization failures; many architectures saturate')
ax.legend(fontsize=9, loc='lower right')

ax = axes[0, 1]
for label, case, color in [('Baseline', baseline, '#245eaa'), ('Class-balanced positives', tier['cases']['class_balanced_focal'], '#1a8b66')]:
    rows = [row for row in case['curve'] if 0 < row['step'] <= 750]
    for index, style, cls in [(0, '-', 'vehicle'), (3, '--', 'cyclist')]:
        ax.plot([row['step'] for row in rows], [aph(row)[index] for row in rows], marker='o', linestyle=style, color=color, markersize=3, label=f'{label}: {cls}')
ax.axhline(.8, color='gray', linestyle='--', linewidth=1)
ax.set(xlabel='Optimizer updates on one fixed frame', ylabel='Native LEVEL2 APH', ylim=(0, 1.04), title='B. Class balancing redistributes learning across classes')
ax.legend(fontsize=8, loc='lower right')

ax = axes[1, 0]
case = tier['cases']['full_bn']
rows = [row for row in case['curve'] if 0 < row['step'] <= 2000]
ax.semilogy([row['step'] for row in rows], [row['evaluation_losses'][0]['total'] for row in rows], 'o-', color='#bd6c0a', label='Full BN: evaluation statistics')
ax.semilogy([row['step'] for row in rows], [row['batch_statistics_losses']['total'] for row in rows], 'o--', color='#bd6c0a', label='Full BN: current batch statistics')
rows = [row for row in baseline['curve'] if 0 < row['step'] <= 2000]
ax.semilogy([row['step'] for row in rows], [row['evaluation_losses'][0]['total'] for row in rows], 'o-', color='#245eaa', label='GN backbone: evaluation statistics')
ax.set(xlabel='Optimizer updates on one fixed frame', ylabel='Total detector loss (log scale)', title='C. BN statistics can hide learned training behavior')
ax.legend(fontsize=8, loc='upper right')

ax = axes[1, 1]
labels = ['Baseline', 'Point attention', 'Point MLP', 'Range fusion', 'Zero range']
cases = [baseline, expanded['cases']['point_attention'], expanded['cases']['point_mlp_control'], expanded['cases']['range_fusion'], expanded['cases']['zero_range_control']]
for i, (cls, color) in enumerate(zip(['Vehicle', 'Pedestrian', 'Sign', 'Cyclist'], ['#245eaa', '#1a8b66', '#bd6c0a', '#8c4a92'])):
    ax.plot([x + (i - 1.5) * .18 for x in range(len(cases))], [aph(at(case, 750))[i] for case in cases], marker='o', linestyle='None', color=color, label=cls, markersize=7)
ax.axhline(.8, color='gray', linestyle='--', linewidth=1)
ax.set_xticks(range(len(labels)), labels, rotation=12)
ax.set(ylabel='Native LEVEL2 APH at the same 750 updates', ylim=(.75, 1.04), title='D. Mechanism controls matter beyond passing the gate')
ax.legend(fontsize=8, loc='lower right', ncol=2)
fig.suptitle('Initial Perception experiments: descriptive signals, not held-out architecture selection', fontsize=14)
fig.savefig(HERE / (STEM + '.png'), dpi=180)
fig.savefig(HERE / (STEM + '.svg'), metadata={'Date': None})
plt.close(fig)
print('Verified summary-to-live-closure equality for 23 trained rows and the separate cap control binding; rebuilt JSON, PNG and SVG.')
print('Host descriptive analysis only; no optimizer execution, new Insula admission or native metric replay.')
