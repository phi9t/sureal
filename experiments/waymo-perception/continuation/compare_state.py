"""CPU comparison of independently pinned legacy producer serialization.

This worker does not update a model, reset RNG, or grant runner admission.
The original native admission remains a separately required parent.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cohort.sustained_replay_values import require_exact_state, require_exact_heads
from continuation.legacy_values import read_json, compare_producer_reports, measurement
from resources.sources import regular


def pinned(reference):
    if type(reference) is not dict or set(reference) != {'path', 'sha256'}:
        raise ValueError('external path and digest required')
    path = Path(reference['path'])
    if not path.is_absolute() or not regular(path):
        raise ValueError('absolute regular evidence path required')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != reference['sha256']:
        raise ValueError('externally pinned evidence bytes changed')
    return path


def _timing(report, state, prior):
    measurement(prior, 'original prior training seconds')
    total = prior
    for row in report['step_records']:
        measurement(row['synchronized_seconds'], 'synchronized update interval')
        total += row['synchronized_seconds']
    measurement(state['training_seconds'], 'checkpoint training_seconds')
    if total != state['training_seconds'] or total != report['cumulative_train_seconds']:
        raise ValueError('checkpoint/report time differs from literal synchronized intervals and original prior')
    if state['steps'] != report['updates'] or state['frame_cursor'] != report['frame_cursor']:
        raise ValueError('checkpoint update/cursor differs from producer report')
    return total


def compare(job):
    keys = {'schema_version', 'original_checkpoint', 'fresh_checkpoint',
            'original_report', 'fresh_report', 'original_heads', 'fresh_heads', 'prior_report'}
    if type(job) is not dict or set(job) != keys or type(job['schema_version']) is not int or job['schema_version'] != 1:
        raise ValueError('complete externally pinned comparison job required')
    old_path = pinned(job['original_checkpoint']); fresh_path = pinned(job['fresh_checkpoint'])
    old_report = read_json(pinned(job['original_report']))
    fresh_report = read_json(pinned(job['fresh_report']))
    for side, report in [('original', old_report), ('fresh', fresh_report)]:
        if report['checkpoint_sha256'] != job[side + '_checkpoint']['sha256']:
            raise ValueError('report does not describe the pinned checkpoint')
        heads = job[side + '_heads']
        if type(heads) is not dict or len(heads) != 16 or set(heads) != set(report['head_hashes']):
            raise ValueError('all sixteen externally pinned frame heads required')
        paths = set()
        for name, reference in heads.items():
            path = pinned(reference)
            if path in paths or reference['sha256'] != report['head_hashes'][name] or path.name != name:
                raise ValueError('unique exact head/report byte identity required')
            paths.add(path)
    compare_producer_reports(old_report, fresh_report)
    old = torch.load(old_path, map_location='cpu', weights_only=True)
    fresh = torch.load(fresh_path, map_location='cpu', weights_only=True)
    require_exact_state(old, fresh, exclude_training_seconds=True)
    prior = 0.0
    if job['prior_report'] is not None:
        prior = read_json(pinned(job['prior_report']))['cumulative_train_seconds']
    _timing(old_report, old, prior)
    total = _timing(fresh_report, fresh, prior)
    for name in job['original_heads']:
        with np.load(pinned(job['original_heads'][name]), allow_pickle=False) as a:
            with np.load(pinned(job['fresh_heads'][name]), allow_pickle=False) as b:
                require_exact_heads({key: a[key] for key in a.files}, {key: b[key] for key in b.files})
    # Recheck every byte identity after loading/comparison.
    for key in ['original_checkpoint', 'fresh_checkpoint', 'original_report', 'fresh_report']:
        pinned(job[key])
    for key in ['original_heads', 'fresh_heads']:
        for ref in job[key].values(): pinned(ref)
    if job['prior_report'] is not None: pinned(job['prior_report'])
    return {'all_state_except_training_seconds_exact': True, 'heads_compared': 16,
            'all_nonmeasurement_producer_fields_exact': True,
            'fresh_synchronized_seconds': total, 'original_training_seconds': old['training_seconds'],
            'updates': old['steps'], 'frame_cursor': old['frame_cursor'],
            'scope': 'serialization/state/head parity only; original native and resource admission remain mandatory'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True); parser.add_argument('--job-sha256', required=True)
    parser.add_argument('--output', required=True); args = parser.parse_args()
    job = read_json(pinned({'path': args.job, 'sha256': args.job_sha256}))
    result = compare(job)
    with Path(args.output).open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')


if __name__ == '__main__': main()
