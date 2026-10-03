"""Scientific parity for bounded replays of immutable native stages.

Producer report parity alone does not admit serialization changes: the caller
must independently establish complete checkpoint and all-head tensor equality.
"""
import json
import math
import datetime
from pathlib import Path
import re


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate JSON field')
        value[key] = item
    return value


def read_json(path):
    try:
        return json.loads(Path(path).read_text(), object_pairs_hook=_pairs,
                          parse_constant=lambda value: _invalid_constant(value))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('readable strict JSON evidence required') from error


def _invalid_constant(value):
    raise ValueError('nonfinite JSON evidence: ' + value)


def require_exact(old, fresh, location='report'):
    if type(old) is not type(fresh):
        raise ValueError('changed value type at ' + location)
    if isinstance(old, dict):
        if old.keys() != fresh.keys():
            raise ValueError('changed field inventory at ' + location)
        for key in old:
            require_exact(old[key], fresh[key], location + '.' + str(key))
    elif isinstance(old, list):
        if len(old) != len(fresh):
            raise ValueError('changed row count at ' + location)
        for index, (a, b) in enumerate(zip(old, fresh)):
            require_exact(a, b, location + '[' + str(index) + ']')
    elif isinstance(old, float) and (not math.isfinite(old) or not math.isfinite(fresh)):
        raise ValueError('nonfinite scientific value at ' + location)
    elif old != fresh:
        raise ValueError('changed scientific value at ' + location)


def measurement(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('finite nonnegative numeric measurement required: ' + name)


def compare_report(old, fresh, excluded):
    if type(old) is not dict or type(fresh) is not dict or old.keys() != fresh.keys():
        raise ValueError('exact report field inventory required')
    if not set(excluded) <= old.keys():
        raise ValueError('all declared measurement fields required')
    for key in excluded:
        measurement(old[key], key); measurement(fresh[key], key)
    require_exact({k: v for k, v in old.items() if k not in excluded},
                  {k: v for k, v in fresh.items() if k not in excluded})


CONTRACTS = {
    'literal-loss': ('check.json', ('elapsed_seconds', 'peak_rss_kib'), ()),
    'export': ('preparation.json', ('elapsed_seconds', 'peak_rss_kib'),
               ('predictions.json', 'groundtruth.json')),
    'proposals': ('check.json', (), ()),
    # elapsed_seconds and peak_rss_kib here belong to the ORIGINAL preparation.
    'score': ('check.json', ('scoring_seconds',),
              ('predictions.bin', 'groundtruth.bin', 'metrics.stdout', 'metrics.stderr')),
    'metrics-audit': ('check.json', (), ('metrics.stdout',)),
}


def compare_stage(stage, original_directory, fresh_directory):
    if stage not in CONTRACTS:
        raise ValueError('explicitly specified legacy stage required')
    report, excluded, files = CONTRACTS[stage]
    old = Path(original_directory); fresh = Path(fresh_directory)
    compare_report(read_json(old / report), read_json(fresh / report), excluded)
    try:
        for name in files:
            a = (old / name).read_bytes(); b = (fresh / name).read_bytes()
            if name == 'metrics.stderr':
                a = stderr_content(a); b = stderr_content(b)
            if a != b:
                raise ValueError('changed native payload: ' + name)
    except OSError as error:
        raise ValueError('complete native payload required') from error


def stderr_content(raw):
    """Tagged headers omit only time; raw lines cannot collide with headers."""
    header = re.compile(rb'^([IWEF])([0-9]{8} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6})( +[0-9]+ )([A-Za-z0-9_./-]+:[0-9]+\] )')
    result = []
    for line in raw.splitlines(keepends=True):
        match = header.match(line)
        if match is not None:
            try:
                datetime.datetime.strptime(match[2].decode('ascii'), '%Y%m%d %H:%M:%S.%f')
            except ValueError as error:
                raise ValueError('invalid glog calendar timestamp') from error
            result.append(('glog', match[1], match[3], match[4], line[match.end():]))
        elif re.match(rb'^[IWEF][0-9]', line):
            raise ValueError('unknown or malformed glog header')
        else:
            result.append(('raw', line))
    return tuple(result)


def compare_producer_reports(old, fresh):
    """Compare scientific values; checkpoint serialization needs a state gate."""
    numeric = {'cumulative_train_seconds', 'elapsed_seconds',
               'peak_allocated_bytes', 'peak_rss_kib'}
    excluded = numeric | {'checkpoint_sha256', 'step_records'}
    if type(old) is not dict or type(fresh) is not dict or old.keys() != fresh.keys():
        raise ValueError('exact producer field inventory required')
    if not excluded <= old.keys():
        raise ValueError('complete producer measurements and serialization required')
    for value in [old, fresh]:
        for key in numeric:
            measurement(value[key], key)
        if not isinstance(value['checkpoint_sha256'], str) or re.fullmatch('[0-9a-f]{64}', value['checkpoint_sha256']) is None:
            raise ValueError('checkpoint byte identity required')
        if type(value['step_records']) is not list:
            raise ValueError('literal producer update records required')
    if len(old['step_records']) != len(fresh['step_records']):
        raise ValueError('changed producer update count')
    for a, b in zip(old['step_records'], fresh['step_records']):
        compare_report(a, b, {'synchronized_seconds'})
    require_exact({k: v for k, v in old.items() if k not in excluded},
                  {k: v for k, v in fresh.items() if k not in excluded})
