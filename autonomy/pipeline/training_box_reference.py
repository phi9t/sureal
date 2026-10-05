"""Independent native-source quantile audit using only the standard library.

No producer, source-adapter, NumPy, or producer validation helper is imported.
The caller must separately establish source hashes and admitted membership.
"""
from collections import Counter
from collections.abc import Mapping
import json
import math


def _same_accounting(actual, expected):
    # JSON comparison also rejects booleans or floats masquerading as row counts.
    if json.dumps(actual, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError('independent native source accounting differs')


def _linear_quantile(ordered, fraction):
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def verify_training_box_distributions(sources, *, reported, membership, expected_scenes):
    """Reopen decoded source iterables and check the producer's full distribution.

    Sources have ``scene``, admitted ``expected_rows`` and native flat ``rows``.
    Equal weight is given to every eligible frame/object, without track dedup.
    Source and geometry validation is deliberately separate from the producer.
    Quantile agreement uses relative and absolute tolerance 1e-12; counts and
    completion inventories must agree exactly, including empty sources.
    """
    if not isinstance(membership, Mapping) or isinstance(expected_scenes, (str, bytes)):
        raise ValueError('admitted native training selection required')
    selection = tuple(expected_scenes)
    if (not selection or any(not isinstance(s, str) or not s for s in selection)
            or len(set(selection)) != len(selection)):
        raise ValueError('unique training source selection required')
    training = {s for s, group in membership.items()
                if isinstance(group, Mapping) and group.get('official_split') == 'training'
                and group.get('research_splits') == ['train']}
    if set(selection) != training:
        raise ValueError('full admitted training selection required')
    if not isinstance(reported, Mapping):
        raise ValueError('producer distribution report required')
    coordinates = {category: [[], [], [], []] for category in (1, 2, 3, 4)}
    tracks = {category: set() for category in coordinates}
    frames, contexts, identities, completed, source_seen = set(), set(), set(), [], set()
    unknown = Counter()
    eligible_rows = 0
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError('native source inventory required')
        scene, expected_rows = source.get('scene'), source.get('expected_rows')
        if (not isinstance(scene, str) or scene not in training or scene in source_seen
                or type(expected_rows) is not int or expected_rows < 0 or 'rows' not in source):
            raise ValueError('unadmitted/duplicate source or bad source inventory')
        source_seen.add(scene)
        source_count, source_eligible, source_unknown = 0, 0, Counter()
        for row in source['rows']:
            if not isinstance(row, Mapping):
                raise ValueError('decoded native row required')
            source_count += 1
            if source_count > expected_rows:
                raise ValueError('source exceeds admitted row inventory')
            try:
                context = row['key.segment_context_name']
                timestamp = row['key.frame_timestamp_micros']
                object_id = row['key.laser_object_id']
                category = row['[LiDARBoxComponent].type']
                center_x = row['[LiDARBoxComponent].box.center.x']
                center_y = row['[LiDARBoxComponent].box.center.y']
                center_z = row['[LiDARBoxComponent].box.center.z']
                length = row['[LiDARBoxComponent].box.size.x']
                width = row['[LiDARBoxComponent].box.size.y']
                height = row['[LiDARBoxComponent].box.size.z']
                heading = row['[LiDARBoxComponent].box.heading']
            except KeyError as error:
                raise ValueError('required native box field missing') from error
            if (context != scene or type(timestamp) is not int or not 0 <= timestamp < 2**63
                    or not isinstance(object_id, str) or not object_id
                    or type(category) is not int or not 0 <= category < 2**31):
                raise ValueError('native source identity differs')
            measurements = (center_x, center_y, center_z, length, width, height, heading)
            if (any(type(x) not in (int, float) or not math.isfinite(x) for x in measurements)
                    or min(length, width, height) <= 0):
                raise ValueError('native geometry is not finite and positive')
            identity = (context, timestamp, object_id)
            if identity in identities:
                raise ValueError('duplicate native frame/object key')
            identities.add(identity)
            if category in coordinates:
                for dimension, value in enumerate((length, width, height, center_z)):
                    coordinates[category][dimension].append(value)
                tracks[category].add((context, object_id))
                frames.add((context, timestamp))
                contexts.add(context)
                eligible_rows += 1
                source_eligible += 1
            else:
                source_unknown[str(category)] += 1
        if source_count != expected_rows:
            raise ValueError('source row inventory incomplete')
        unknown.update(source_unknown)
        completed.append({'scene': scene, 'native_rows': source_count,
                          'eligible_box_rows': source_eligible,
                          'outside_box_class_counts': dict(sorted(source_unknown.items()))})
    if source_seen != training:
        raise ValueError('native training source omitted')
    expected_accounting = {
        'rows': eligible_rows, 'frames': len(frames), 'observed_scenes': sorted(contexts),
        'native_rows': sum(source['native_rows'] for source in completed),
        'completed_sources': sorted(source_seen),
        'source_completion': sorted(completed, key=lambda source: source['scene']),
        'outside_box_class_counts': dict(sorted(unknown.items())),
    }
    for field, value in expected_accounting.items():
        if field not in reported:
            raise ValueError('producer source accounting missing')
        _same_accounting(reported[field], value)
    classes = reported.get('classes')
    if not isinstance(classes, Mapping) or set(classes) != {'1', '2', '3', '4'}:
        raise ValueError('native class inventory differs')
    verified = {}
    for category, columns in coordinates.items():
        class_report = classes[str(category)]
        if not isinstance(class_report, Mapping):
            raise ValueError('native class statistics missing')
        _same_accounting(class_report.get('box_rows'), len(columns[0]))
        _same_accounting(class_report.get('unique_tracks'), len(tracks[category]))
        ordered = [sorted(column) for column in columns]
        reference = {}
        for field, fraction in [('median_length_width_height_center_z', .5),
                                ('p10_length_width_height_center_z', .1),
                                ('p90_length_width_height_center_z', .9)]:
            if field not in class_report:
                raise ValueError('native quantile missing')
            actual = class_report[field]
            if not columns[0]:
                if actual is not None:
                    raise ValueError('absent class acquired default statistics')
                reference[field] = None
                continue
            expected = [_linear_quantile(column, fraction) for column in ordered]
            if (not isinstance(actual, list) or len(actual) != 4
                    or any(type(x) not in (int, float) or not math.isfinite(x) for x in actual)
                    or any(not math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12)
                           for x, y in zip(actual, expected))):
                raise ValueError('independent native quantiles differ')
            reference[field] = expected
        verified[str(category)] = reference
    return {'status': 'native source accounting and quantiles independently verified',
            'completed_sources': len(completed), 'native_rows': expected_accounting['native_rows'],
            'eligible_box_rows': eligible_rows, 'reference_quantiles': verified,
            'scope': 'decoded native distributions only; caller verifies source/runtime hashes; no anchor adoption'}
