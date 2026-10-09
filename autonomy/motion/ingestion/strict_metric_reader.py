"""Strict reader for native Waymo motion metric JSON reports."""
import math

OBJECT_FILTERS={1:'TYPE_VEHICLE',2:'TYPE_PEDESTRIAN',3:'TYPE_CYCLIST'}
ZERO_OMITTABLE_FIELDS=frozenset((
    'minAde',
    'minFde',
    'missRate',
    'overlapRate',
    'meanAveragePrecision',
    'softMeanAveragePrecision',
))
COUNT_FIELDS=('min_ade','min_fde','miss_rate','overlap_rate')
RATE_FIELDS=frozenset(('missRate','overlapRate','meanAveragePrecision','softMeanAveragePrecision'))

def _number(value, *, rate=False):
    if isinstance(value,bool):
        raise ValueError('invalid motion metric value')
    try:
        result=float(value)
    except (TypeError,ValueError) as error:
        raise ValueError('invalid motion metric value') from error
    if not math.isfinite(result) or (rate and not 0 <= result <= 1):
        raise ValueError('invalid motion metric value')
    return result

def _integer(value):
    if isinstance(value,bool) or not isinstance(value,int) or value<0:
        raise ValueError('invalid motion count')
    return value

def _normalize_expected_counts(expected_counts):
    if expected_counts is None:
        return None
    result={}
    for kind,counts in expected_counts.items():
        result[int(kind)]={name:_integer(counts[name]) for name in COUNT_FIELDS}
    return result

def parse_result(report, expected_counts=None, *, expected_filters=OBJECT_FILTERS, measurement_step=15):
    if not isinstance(report,dict):
        raise ValueError('motion metric report must be an object')
    expected_counts=_normalize_expected_counts(expected_counts)
    try:
        bundles=report['metrics']['metricsBundles']
        counts=report['counts']
    except (KeyError,TypeError) as error:
        raise ValueError('motion metric report is incomplete') from error
    if not isinstance(bundles,list) or not isinstance(counts,list):
        raise ValueError('motion metric report is incomplete')
    count_by_kind={}
    for row in counts:
        if not isinstance(row,dict):raise ValueError('motion count row must be an object')
        kind=_integer(row.get('object_type'))
        if kind not in expected_filters or kind in count_by_kind:
            raise ValueError('unknown or duplicate motion count class')
        if _integer(row.get('measurement_step'))!=measurement_step:
            raise ValueError('motion measurement step mismatch')
        count_by_kind[kind]={name:_integer(row.get(name)) for name in COUNT_FIELDS}
    bundle_by_filter={}
    for row in bundles:
        if not isinstance(row,dict):raise ValueError('motion metric bundle must be an object')
        if 'objectFilter' not in row or 'measurementStep' not in row:
            raise ValueError('motion metric bundle is missing structural fields')
        object_filter=row['objectFilter']
        if object_filter not in expected_filters.values() or object_filter in bundle_by_filter:
            raise ValueError('unknown or duplicate motion objectFilter')
        if _integer(row['measurementStep'])!=measurement_step:
            raise ValueError('motion measurement step mismatch')
        bundle_by_filter[object_filter]=row
    if set(bundle_by_filter)!={expected_filters[k] for k in count_by_kind}:
        raise ValueError('motion class identity mismatch')
    if expected_counts is not None and count_by_kind!=expected_counts:
        raise ValueError('motion count mismatch')
    classes={}
    for kind,object_filter in expected_filters.items():
        if kind not in count_by_kind:
            continue
        bundle=bundle_by_filter[object_filter]
        parsed={'objectFilter':object_filter,'measurementStep':measurement_step,'counts':count_by_kind[kind]}
        for field in ZERO_OMITTABLE_FIELDS:
            parsed[field]=_number(bundle.get(field,0.0),rate=field in RATE_FIELDS)
        custom=bundle.get('customMetrics',{})
        if not isinstance(custom,dict):
            raise ValueError('motion customMetrics must be an object')
        parsed['customMetrics']=custom
        classes[kind]=parsed
    return {'measurement_step':measurement_step,'classes':classes}

def class_metrics(report, object_type, expected_counts=None, *, expected_filters=OBJECT_FILTERS, measurement_step=15):
    parsed=parse_result(report,expected_counts,expected_filters=expected_filters,measurement_step=measurement_step)
    kind=_integer(object_type)
    try:
        return parsed['classes'][kind]
    except KeyError as error:
        raise ValueError('motion class missing') from error
