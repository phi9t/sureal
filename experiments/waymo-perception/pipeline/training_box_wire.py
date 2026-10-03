"""Verified streaming of immutable box Parquet into an offline Insula worker.

Only one source payload is decoded at a time. Callers independently admit source
metadata and membership, and must fully consume the source/row iterators before
publishing statistics. Native geometry validation belongs to each downstream
producer or independent reference consumer.
"""
import base64
import hashlib
import json
import re

import pyarrow as pa
import pyarrow.parquet as pq


_HEADER_BYTES = 4096
_FIELDS = {'scene', 'bytes', 'native_rows', 'sha256', 'md5_base64'}
_COLUMNS = [
    'key.segment_context_name', 'key.frame_timestamp_micros', 'key.laser_object_id',
    '[LiDARBoxComponent].type', '[LiDARBoxComponent].box.center.x',
    '[LiDARBoxComponent].box.center.y', '[LiDARBoxComponent].box.center.z',
    '[LiDARBoxComponent].box.size.x', '[LiDARBoxComponent].box.size.y',
    '[LiDARBoxComponent].box.size.z', '[LiDARBoxComponent].box.heading',
]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate wire header key')
        result[key] = value
    return result


def _header(stream):
    line = stream.readline(_HEADER_BYTES + 1)
    if not isinstance(line, bytes) or not line.endswith(b'\n') or len(line) > _HEADER_BYTES:
        raise ValueError('bounded complete source header required')
    try:
        value = json.loads(line.decode('utf-8'), object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError) as error:
        raise ValueError('invalid source wire header') from error
    if not isinstance(value, dict):
        raise ValueError('source wire header must be an object')
    return value


def _same_header(actual, expected):
    if json.dumps(actual, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError('wire source identity/order differs from admitted inventory')


def _exact_bytes(stream, count):
    chunks, remaining = [], count
    while remaining:
        block = stream.read(min(65536, remaining))
        if not isinstance(block, bytes) or not block or len(block) > remaining:
            raise ValueError('source payload truncated or invalid read')
        chunks.append(block)
        remaining -= len(block)
    return b''.join(chunks)


def stream_training_box_sources(stream, *, inventory, acknowledge=None):
    """Yield decoded sources from length-bound, hash-pinned stdin packets.

    Each packet is a JSON-line header exactly matching one inventory entry,
    followed by that entry's byte count of raw Parquet. Inventory entries contain
    scene, bytes, native_rows, sha256 and md5_base64. A final JSON line must be
    ``{"kind": "end", "sources": N}``, followed by EOF. Headers are capped at
    4096 bytes; payload lengths come only from the caller's admitted inventory.
    Acknowledgements contain scene/digest/actual rows and occur only after every
    row of that source has been consumed. An error prevents aggregate completion.
    """
    sources, seen = [], set()
    for entry in inventory:
        if not isinstance(entry, dict) or set(entry) != _FIELDS:
            raise ValueError('complete admitted source wire inventory required')
        source = dict(entry)
        if (not isinstance(source['scene'], str) or not source['scene'] or source['scene'] in seen
                or type(source['bytes']) is not int or source['bytes'] <= 0
                or type(source['native_rows']) is not int or source['native_rows'] < 0
                or not isinstance(source['sha256'], str)
                or not re.fullmatch('[0-9a-f]{64}', source['sha256'])
                or not isinstance(source['md5_base64'], str)):
            raise ValueError('invalid or duplicate admitted source wire inventory')
        try:
            md5 = base64.b64decode(source['md5_base64'], validate=True)
        except ValueError as error:
            raise ValueError('invalid admitted source MD5') from error
        if len(md5) != 16:
            raise ValueError('invalid admitted source MD5 length')
        seen.add(source['scene'])
        sources.append(source)
    if not sources:
        raise ValueError('nonempty admitted source inventory required')
    for source in sources:
        _same_header(_header(stream), source)
        payload = _exact_bytes(stream, source['bytes'])
        if (hashlib.sha256(payload).hexdigest() != source['sha256']
                or base64.b64encode(hashlib.md5(payload, usedforsecurity=False).digest()).decode()
                != source['md5_base64']):
            raise ValueError('wire source SHA256/MD5 differs')
        parquet = pq.ParquetFile(pa.BufferReader(payload))
        if (parquet.metadata.num_rows != source['native_rows']
                or not set(_COLUMNS).issubset(parquet.schema_arrow.names)):
            raise ValueError('native source schema or row inventory differs')
        state = {'finished': False, 'rows': 0}

        def rows(parquet=parquet, expected=source['native_rows'], state=state):
            for batch in parquet.iter_batches(batch_size=4096, columns=_COLUMNS):
                for row in batch.to_pylist():
                    state['rows'] += 1
                    yield row
            if state['rows'] != expected:
                raise ValueError('decoded native row inventory differs')
            state['finished'] = True

        yield {'scene': source['scene'], 'expected_rows': source['native_rows'], 'rows': rows()}
        if not state['finished']:
            raise ValueError('native rows not fully consumed; source cannot be acknowledged')
        if acknowledge is not None:
            acknowledge({'scene': source['scene'], 'sha256': source['sha256'],
                         'native_rows': state['rows'], 'status': 'consumed'})
        del payload, parquet, rows
    _same_header(_header(stream), {'kind': 'end', 'sources': len(sources)})
    if stream.read(1) != b'':
        raise ValueError('trailing data after complete source inventory')
