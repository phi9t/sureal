"""Validate the entire exported catalog before per-frame geometry audits."""
from collections import Counter


def validate_catalog(manifest, reports, predictions, groundtruth):
    identities = [frame['identity'] for frame in manifest['frames']]
    if len(set(identities)) != len(identities):
        raise ValueError('duplicate manifest frame')
    if [report['identity'] for report in reports] != identities:
        raise ValueError('frame reports must match manifest order exactly')
    allowed = set(identities)
    for records, count_key in ((predictions, 'predictions'),
                               (groundtruth, 'native_groundtruth')):
        counts = Counter()
        seen = set()
        for record in records:
            timestamp = record['frame_timestamp_micros']
            context = record['context_name']
            if type(timestamp) is not int or not isinstance(context, str):
                raise ValueError('invalid catalog frame key')
            identity = context + ':' + str(timestamp)
            if identity not in allowed:
                raise ValueError('catalog record outside manifest frames')
            object_id = record['object_id']
            if not isinstance(object_id, str) or not object_id:
                raise ValueError('missing catalog object identity')
            key = (identity, object_id)
            if key in seen:
                raise ValueError('duplicate object identity within frame')
            seen.add(key)
            counts[identity] += 1
        for report in reports:
            count = report[count_key]
            if type(count) is not int or count < 0 or counts[report['identity']] != count:
                raise ValueError('catalog frame count differs from report')
