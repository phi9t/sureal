"""Complete native training-source accounting before distribution publication.

Callers admit and hash-pin membership and source bytes before invoking this
adapter. It checks decoded content and completeness, not cryptographic provenance.
Source rows may stream; no partial report is returned when a source fails.
"""
from collections import Counter
from collections.abc import Mapping
import math

from .training_box_statistics import training_box_statistics


_BOX_FIELDS = ('center.x', 'center.y', 'center.z', 'size.x', 'size.y', 'size.z', 'heading')


def _native_record(row, scene):
    if not isinstance(row, Mapping):
        raise ValueError('native decoded row required')
    try:
        context = row['key.segment_context_name']
        timestamp = row['key.frame_timestamp_micros']
        identity = row['key.laser_object_id']
        category = row['[LiDARBoxComponent].type']
        box = [row[f'[LiDARBoxComponent].box.{field}'] for field in _BOX_FIELDS]
    except KeyError as error:
        raise ValueError('native identity or box field missing') from error
    if (context != scene or type(timestamp) is not int or not 0 <= timestamp < 2**63
            or not isinstance(identity, str) or not identity
            or type(category) is not int or not 0 <= category < 2**31):
        raise ValueError('native source context/frame/object/category differs')
    if (any(type(value) not in (int, float) or not math.isfinite(value) for value in box)
            or any(value <= 0 for value in box[3:6])):
        raise ValueError('finite native box with positive dimensions required')
    return {'context_name': context, 'frame_timestamp_micros': timestamp,
            'object_id': identity, 'type': category, 'box': box}


def training_box_statistics_from_sources(sources, *, membership, expected_scenes):
    """Consume each declared source once, including sources with no eligible rows.

    Each source supplies ``scene``, nonnegative integer ``expected_rows`` from its
    admitted inventory, and an iterable of flattened native Parquet ``rows``.
    All declared training scenes must be included. Unknown categories are counted
    separately after identity/geometry validation; they cannot hide duplicate rows.
    Geometry uses native vehicle-reference center-Z and length/width/height.
    """
    if isinstance(expected_scenes, (str, bytes)) or not isinstance(membership, Mapping):
        raise ValueError('explicit admitted training scene inventory required')
    expected = tuple(expected_scenes)
    if (not expected or any(not isinstance(scene, str) or not scene for scene in expected)
            or len(set(expected)) != len(expected)):
        raise ValueError('unique nonempty training scene inventory required')
    admitted_training = {scene for scene, group in membership.items()
                         if isinstance(group, Mapping) and group.get('official_split') == 'training'
                         and group.get('research_splits') == ['train']}
    if set(expected) != admitted_training:
        raise ValueError('complete admitted training-only scene selection required')
    completed = []
    outside_counts = Counter()

    def records():
        seen_sources = set()
        for source in sources:
            if not isinstance(source, Mapping):
                raise ValueError('native source inventory required')
            scene = source.get('scene')
            count_expected = source.get('expected_rows')
            if (scene not in admitted_training or scene in seen_sources
                    or type(count_expected) is not int or count_expected < 0 or 'rows' not in source):
                raise ValueError('extra/duplicate source or invalid source row inventory')
            seen_sources.add(scene)
            seen_rows = set()
            count = 0
            eligible = 0
            outside = Counter()
            for row in source['rows']:
                count += 1
                if count > count_expected:
                    raise ValueError('decoded row count exceeds admitted source inventory')
                record = _native_record(row, scene)
                key = (record['frame_timestamp_micros'], record['object_id'])
                if key in seen_rows:
                    raise ValueError('duplicate native frame/object row')
                seen_rows.add(key)
                if record['type'] in (1, 2, 3, 4):
                    eligible += 1
                    yield record
                else:
                    outside[str(record['type'])] += 1
            if count != count_expected:
                raise ValueError('decoded row count differs from admitted source inventory')
            outside_counts.update(outside)
            completed.append({'scene': scene, 'native_rows': count, 'eligible_box_rows': eligible,
                              'outside_box_class_counts': dict(sorted(outside.items()))})
        if seen_sources != admitted_training:
            raise ValueError('required training source omitted')

    report = training_box_statistics(records(), membership=membership)
    report.update(completed_sources=sorted(source['scene'] for source in completed),
                  source_completion=sorted(completed, key=lambda source: source['scene']),
                  native_rows=sum(source['native_rows'] for source in completed),
                  outside_box_class_counts=dict(sorted(outside_counts.items())))
    return report
