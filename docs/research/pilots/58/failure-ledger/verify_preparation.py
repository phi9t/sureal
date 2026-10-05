"""Bounded 58.A evidence reconciliation; neither inference nor a complete 42 tool."""
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import re
import time

import numpy as np


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def schema_check(value, spec):
    types = {'object': dict, 'array': list, 'string': str, 'integer': int,
             'number': (int, float), 'boolean': bool, 'null': type(None)}
    declared = spec.get('type')
    if declared:
        declared = [declared] if isinstance(declared, str) else declared
        assert any(isinstance(value, types[t]) and
                   not (t in ('integer', 'number') and isinstance(value, bool))
                   for t in declared), (value, declared)
    if 'const' in spec:
        assert value == spec['const']
    if 'enum' in spec:
        assert value in spec['enum']
    if isinstance(value, dict):
        assert set(spec.get('required', ())) <= set(value)
        if spec.get('additionalProperties') is False:
            assert set(value) <= set(spec.get('properties', {}))
        for key, child in spec.get('properties', {}).items():
            if key in value:
                schema_check(value[key], child)
    if isinstance(value, list) and 'items' in spec:
        for item in value:
            schema_check(item, spec['items'])


def main():
    started = time.monotonic()
    doc = Path('/experiment')
    provenance = read(doc / 'provenance.json')
    files = {r['id']: r for r in provenance['verified_files']}
    for item in files.values():
        assert sha(item['live_path']) == item['sha256'], item['id']
    manifest = read(files['native_manifest']['live_path'])
    truth = read(files['native_groundtruth']['live_path'])
    archived = read(files['cause_check']['live_path'])
    cause_receipt = read(files['cause_receipt']['live_path'])
    assert archived == cause_receipt['validation']
    oracle = read(files['oracle_check']['live_path'])
    metrics = read(files['native_metrics_receipt']['live_path'])['validation']
    index = {}
    by_frame = collections.defaultdict(list)
    for record in truth:
        identity = record['context_name'] + ':' + str(record['frame_timestamp_micros'])
        key = (identity, record['object_id'])
        assert key not in index
        index[key] = record
        by_frame[identity].append(record)
    assert set(by_frame) == {f['identity'] for f in manifest['frames']}
    counts = {name: collections.Counter() for name in
              ('native', 'positive_native', 'training_eligible', 'covered', 'uncovered')}
    frame_results = []
    missing_keys = set()
    for frame in manifest['frames']:
        identity = frame['identity']
        records = by_frame[identity]
        eligible = sorted([r for r in records if r['num_lidar_points_in_box'] > 0
                           and all(lo <= x < hi for x, lo, hi in
                                   zip(r['box'][:3], [-64, -64, -4], [64, 64, 6]))],
                          key=lambda r: r['object_id'])
        report = read(files['report:' + identity]['live_path'])
        assert [r['object_id'] for r in eligible] == report['eligible_object_ids']
        assert len(records) == report['target_assignment']['native_box_rows']
        with np.load(files['targets:' + identity]['live_path'], allow_pickle=False) as target:
            labels = target['labels']
            assigned = target['target_indices']
            assert labels.shape == assigned.shape == (524288,)
            covered = set(assigned[labels > 0].tolist())
            assert all(0 <= i < len(eligible) for i in covered)
            positive_counts = collections.Counter(assigned[labels > 0].tolist())
        missing = {r['object_id'] for i, r in enumerate(eligible) if i not in covered}
        assert missing == set(report['target_assignment']['uncovered_object_ids'])
        archived_frame = next(f for f in archived['frames'] if f['identity'] == identity)
        assert missing == {r['object_id'] for r in archived_frame['uncovered']}
        for record in records:
            counts['native'][str(record['type'])] += 1
            if record['num_lidar_points_in_box'] > 0:
                counts['positive_native'][str(record['type'])] += 1
        for i, record in enumerate(eligible):
            counts['training_eligible'][str(record['type'])] += 1
            counts['covered' if i in covered else 'uncovered'][str(record['type'])] += 1
            if i not in covered:
                missing_keys.add((identity, record['object_id']))
                assert positive_counts[i] == 0
        frame_results.append({'identity': identity, 'native': len(records),
                              'training_eligible': len(eligible),
                              'covered': len(covered), 'uncovered': len(missing)})
    normalized = {name: {str(c): count[str(c)] for c in range(1, 5)}
                  for name, count in counts.items()}
    expected = read(doc / 'reconciliation.json')
    assert normalized == expected['by_class']
    assert frame_results == expected['frames']
    assert sum(counts['native'].values()) == metrics['native_groundtruth'] == 1279
    assert sum(counts['training_eligible'].values()) == metrics['training_eligible_groundtruth'] == 1053
    assert sum(counts['uncovered'].values()) == archived['uncovered_objects'] == 30
    for a, b in [('positive_native', 'positive_native'),
                 ('training_eligible', 'training_roi'), ('covered', 'anchor_covered')]:
        assert normalized[a] == oracle['counts'][b]
    examples = read(doc / 'uncovered-rows.json')
    row_schema = read(doc / 'row-schema.json')
    row_keys = set()
    for row in examples['rows']:
        schema_check(row, row_schema)
        key = (row['frame_identity'], row['object_id'])
        assert key not in row_keys
        row_keys.add(key)
        native = index[key]
        assert row['native_class'] == native['type']
        assert row['native_num_lidar_points_in_box'] == native['num_lidar_points_in_box']
        assert row['native_difficulty'] == native['difficulty']
        detail = next(r for f in archived['frames'] if f['identity'] == key[0]
                      for r in f['uncovered'] if r['object_id'] == key[1])
        assert row['assignment_audit'] == detail
        for winner in detail['winners']:
            assert index[(key[0], winner['object_id'])]['type'] == winner['class']
        assert row['source_ids'] == ['native_groundtruth', 'cause_check',
                                     'report:' + key[0], 'targets:' + key[0]]
    assert row_keys == missing_keys
    assert importlib.util.find_spec('tensorflow') is None
    assert not any(Path('/dev').glob('nvidia*'))
    assert not Path('/dev/dri').exists()
    repository_doc = Path('/tmp/repository/docs/research/pilots/58/failure-ledger')
    links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', (doc / 'README.md').read_text())
    for link in links:
        assert not link.startswith(('http:', 'https:'))
        assert (repository_doc / link).resolve().is_file(), link
    output = {'passed': True, 'scope': 'fresh CPU Insula evidence/schema reconciliation; '
              'archived cause values reopened, no literal assignment rerun or model/native metric replay',
              'verified_file_count': len(files), 'native_objects': len(index),
              'training_eligible': 1053, 'uncovered_rows': len(row_keys),
              'by_class': normalized, 'frames': frame_results,
              'tensorflow_absent': True, 'gpu_devices_absent': True,
              'optimizer_updates': 0, 'elapsed_seconds': time.monotonic() - started,
              'document_links_checked': len(links),
              'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'document_sha256': {p.name: sha(p) for p in doc.iterdir()
                                 if p.is_file() and p.name != 'live-receipt.json'}}
    Path('/outputs/check.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2), flush=True)


if __name__ == '__main__':
    main()
