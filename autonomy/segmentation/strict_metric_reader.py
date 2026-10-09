"""Strict reader for native Waymo semantic segmentation metric reports."""
import math
import re

EXPECTED_CLASSES=frozenset((
    'TYPE_TRAFFIC_LIGHT',
    'TYPE_BUILDING',
    'TYPE_OTHER_VEHICLE',
    'TYPE_MOTORCYCLE',
    'TYPE_ROAD',
    'TYPE_BUS',
    'TYPE_SIGN',
    'TYPE_CURB',
    'TYPE_SIDEWALK',
    'TYPE_PEDESTRIAN',
    'TYPE_BICYCLE',
    'TYPE_TRUCK',
    'TYPE_WALKABLE',
    'TYPE_CONSTRUCTION_CONE',
    'TYPE_TREE_TRUNK',
    'TYPE_CAR',
    'TYPE_BICYCLIST',
    'TYPE_OTHER_GROUND',
    'TYPE_VEGETATION',
    'TYPE_MOTORCYCLIST',
    'TYPE_POLE',
    'TYPE_LANE_MARKER',
))

_NUMBER=r'[-+]?(?:nan|inf|\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'

def _metric_value(text):
    try:
        value=float(text)
    except ValueError as error:
        raise ValueError('invalid segmentation metric value') from error
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('invalid segmentation metric value')
    return value

def parse_result(stdout, expected_classes=EXPECTED_CLASSES):
    expected=set(expected_classes)
    if not expected:
        raise ValueError('segmentation class configuration required')
    lines=[line.strip() for line in stdout.splitlines() if line.strip()]
    classes={}
    miou=None
    frames={}
    processed=[]
    for line in lines:
        match=re.fullmatch(r'(\d+) frames found in prediction\.',line)
        if match:
            if 'prediction' in frames:raise ValueError('duplicate segmentation prediction count')
            frames['prediction']=int(match.group(1));continue
        match=re.fullmatch(r'(\d+) frames found in groundtruth\.',line)
        if match:
            if 'groundtruth' in frames:raise ValueError('duplicate segmentation groundtruth count')
            frames['groundtruth']=int(match.group(1));continue
        match=re.fullmatch(r'Processing example (\d+) out of (\d+)',line)
        if match:
            current,total=(int(match.group(1)),int(match.group(2)))
            if current<0 or total<=0 or current>=total:raise ValueError('invalid segmentation progress line')
            processed.append((current,total));continue
        match=re.fullmatch(fr'(TYPE_[A-Z_]+):({_NUMBER})',line)
        if match:
            name,value=match.groups()
            if name not in expected or name in classes:
                raise ValueError('unexpected or duplicate segmentation class')
            classes[name]=_metric_value(value);continue
        match=re.fullmatch(fr'miou=({_NUMBER})',line)
        if match:
            if miou is not None:raise ValueError('duplicate segmentation miou')
            miou=_metric_value(match.group(1));continue
        raise ValueError('unrecognized segmentation metric output')
    if frames.keys()!={'prediction','groundtruth'} or frames['prediction']!=frames['groundtruth']:
        raise ValueError('missing or inconsistent segmentation frame counts')
    if processed != [(index,frames['prediction']) for index in range(frames['prediction'])]:
        raise ValueError('segmentation progress must cover every frame in order')
    if set(classes)!=expected:
        raise ValueError('incomplete segmentation class metrics')
    if miou is None:
        raise ValueError('missing segmentation miou')
    return {'frames':frames,'examples_processed':[index for index,_ in processed],
            'classes':classes,'miou':miou}

def require_perfect_self_score(stdout, expected_classes=EXPECTED_CLASSES):
    parsed=parse_result(stdout,expected_classes)
    if abs(parsed['miou']-1.0)>1e-6:
        raise ValueError('segmentation self-score miou is not one')
    if any(abs(value-1.0)>1e-6 for value in parsed['classes'].values()):
        raise ValueError('segmentation self-score class metric is not one')
    return parsed
