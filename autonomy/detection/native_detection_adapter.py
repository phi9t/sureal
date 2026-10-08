"""Fail-closed parser for the pinned default 3D detection CLI.

Expected breakdown names must come from the frozen evaluation configuration,
not from the output being validated. This parser is not a LET/2D adapter.
"""
import math
import re

EXPECTED_DEFAULT_BREAKDOWNS=frozenset((
    'OBJECT_TYPE_TYPE_VEHICLE_LEVEL_1',
    'OBJECT_TYPE_TYPE_VEHICLE_LEVEL_2',
    'OBJECT_TYPE_TYPE_PEDESTRIAN_LEVEL_1',
    'OBJECT_TYPE_TYPE_PEDESTRIAN_LEVEL_2',
    'OBJECT_TYPE_TYPE_SIGN_LEVEL_1',
    'OBJECT_TYPE_TYPE_SIGN_LEVEL_2',
    'OBJECT_TYPE_TYPE_CYCLIST_LEVEL_1',
    'OBJECT_TYPE_TYPE_CYCLIST_LEVEL_2',
    'RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_1',
    'RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_2',
    'RANGE_TYPE_VEHICLE_[30, 50)_LEVEL_1',
    'RANGE_TYPE_VEHICLE_[30, 50)_LEVEL_2',
    'RANGE_TYPE_VEHICLE_[50, +inf)_LEVEL_1',
    'RANGE_TYPE_VEHICLE_[50, +inf)_LEVEL_2',
    'RANGE_TYPE_PEDESTRIAN_[0, 30)_LEVEL_1',
    'RANGE_TYPE_PEDESTRIAN_[0, 30)_LEVEL_2',
    'RANGE_TYPE_PEDESTRIAN_[30, 50)_LEVEL_1',
    'RANGE_TYPE_PEDESTRIAN_[30, 50)_LEVEL_2',
    'RANGE_TYPE_PEDESTRIAN_[50, +inf)_LEVEL_1',
    'RANGE_TYPE_PEDESTRIAN_[50, +inf)_LEVEL_2',
    'RANGE_TYPE_SIGN_[0, 30)_LEVEL_1',
    'RANGE_TYPE_SIGN_[0, 30)_LEVEL_2',
    'RANGE_TYPE_SIGN_[30, 50)_LEVEL_1',
    'RANGE_TYPE_SIGN_[30, 50)_LEVEL_2',
    'RANGE_TYPE_SIGN_[50, +inf)_LEVEL_1',
    'RANGE_TYPE_SIGN_[50, +inf)_LEVEL_2',
    'RANGE_TYPE_CYCLIST_[0, 30)_LEVEL_1',
    'RANGE_TYPE_CYCLIST_[0, 30)_LEVEL_2',
    'RANGE_TYPE_CYCLIST_[30, 50)_LEVEL_1',
    'RANGE_TYPE_CYCLIST_[30, 50)_LEVEL_2',
    'RANGE_TYPE_CYCLIST_[50, +inf)_LEVEL_1',
    'RANGE_TYPE_CYCLIST_[50, +inf)_LEVEL_2',
))

_GLOG_PREINIT='WARNING: Logging before InitGoogleLogging() is written to STDERR'
_GLOG_DIAGNOSTIC=re.compile(
    r'^W\d{8} \d\d:\d\d:\d\d\.\d+\s+\d+ iou\.cc:(172|216)\] '
    r'(Tiny|Huge) box dim seen, return 0\.0 IOU\.$')
_BOX_NUMBER=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
_BOX_FIELDS=('center_y','center_z','width','length','height','heading')

def _consume_box(label, lines, index):
    if index>=len(lines) or re.fullmatch(fr'{label}: center_x: {_BOX_NUMBER}',lines[index]) is None:
        raise ValueError('unexpected diagnostic box dump')
    index+=1
    for field in _BOX_FIELDS:
        if index>=len(lines) or re.fullmatch(fr'{field}: {_BOX_NUMBER}',lines[index]) is None:
            raise ValueError('unexpected diagnostic box dump')
        index+=1
    return index

def _parse_diagnostics(stderr):
    diagnostics={}
    lines=stderr.splitlines()
    index=0
    while index<len(lines):
        line=lines[index]
        if line==_GLOG_PREINIT:
            diagnostics['glog_preinit']=diagnostics.get('glog_preinit',0)+1
            index+=1
            continue
        match=_GLOG_DIAGNOSTIC.fullmatch(line)
        if match is None:
            raise ValueError('unexpected evaluator diagnostics')
        line_no,kind=match.groups()
        key=f'iou.cc:{line_no} {kind} box dim seen'
        diagnostics[key]=diagnostics.get(key,0)+1
        index=_consume_box('b1',lines,index+1)
        if index>=len(lines) or lines[index] != '':
            raise ValueError('unexpected diagnostic box dump')
        index=_consume_box('b2',lines,index+1)
    return diagnostics

def parse_result(exit_code, stdout, stderr, expected_breakdowns=None):
    expected=set(EXPECTED_DEFAULT_BREAKDOWNS if expected_breakdowns is None else expected_breakdowns)
    if exit_code != 0 or not expected:
        raise ValueError('evaluator failed or lacks configuration')
    diagnostics=_parse_diagnostics(stderr) if stderr.strip() else {}
    lines=[line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines or not re.fullmatch(r'\d+ examples found\.',lines[0]):
        raise ValueError('missing native example count')
    metrics={}
    for line in lines[1:]:
        match=re.fullmatch(r'(.+): \[mAP ([^\]]+)\] \[mAPH ([^\]]+)\]',line)
        if match is None:
            raise ValueError('unrecognized metric output')
        name,ap,aph=match.groups()
        if name not in expected or name in metrics:
            raise ValueError('unexpected or duplicate breakdown')
        values=[float(ap),float(aph)]
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise ValueError('invalid metric value')
        metrics[name]=dict(zip(('AP','APH'),values))
    if set(metrics)!=expected:
        raise ValueError('incomplete metric breakdowns')
    return {'examples':int(lines[0].split()[0]),'metrics':metrics,'diagnostics':diagnostics}
