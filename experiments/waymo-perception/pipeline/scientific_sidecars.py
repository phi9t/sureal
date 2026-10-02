"""Decode native component rows into bounded, sensor-indexed scene sidecars."""
import hashlib
import io
import json
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from .sensor_records import select_rows, array_field

SUPPORTED = {'lidar_calibration', 'camera_calibration', 'vehicle_pose',
             'lidar_pose', 'lidar_camera_projection', 'lidar_segmentation', 'lidar_box'}


def materialize_component(source, component, scene, output, remaining_bytes):
    source, output = Path(source), Path(output)
    if component not in SUPPORTED:
        raise ValueError('component has no declared sidecar contract')
    if type(remaining_bytes) is not int or remaining_bytes <= 0:
        raise ValueError('derived capacity must be a positive integer')
    if output.exists():
        raise ValueError('sidecar destination already exists; never overwrite')
    output.mkdir(parents=True)
    with source.open('rb') as stream:
        source_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    native_schema = pq.ParquetFile(source).schema_arrow
    shaped = sorted(name[:-6] for name in native_schema.names if name.endswith('.shape'))
    rows, seen, used = [], set(), 0

    def encode(value):
        return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()

    def write(name, data):
        nonlocal used
        if used + len(data) > remaining_bytes:
            raise ValueError('decoded component exceeds derived working-set capacity')
        (output/name).write_bytes(data)
        used += len(data)
        return hashlib.sha256(data).hexdigest()

    for index, row in enumerate(select_rows(source)):
        keys = {name: value for name, value in row.items() if name.startswith('key.')}
        if keys.get('key.segment_context_name') != scene:
            raise ValueError('wrong native scene')
        if 'key.frame_timestamp_micros' in keys:
            stamp = keys['key.frame_timestamp_micros']
            if type(stamp) is not int or stamp < 0:
                raise ValueError('invalid native timestamp')
        for name in ('key.laser_name', 'key.camera_name'):
            if name in keys and (type(keys[name]) is not int or not 1 <= keys[name] <= 5):
                raise ValueError('invalid Perception sensor identity')
        identity = json.dumps(keys, sort_keys=True, separators=(',', ':'))
        if identity in seen:
            raise ValueError('duplicate native component identity')
        seen.add(identity)
        arrays, aliases = {}, {}
        for prefix in shaped:
            if prefix+'.values' not in row:
                raise ValueError('shape without declared value field')
            shape = row[prefix+'.shape']
            if shape is not None and any(type(n) is not int or n <= 0 for n in shape):
                raise ValueError('invalid native array shape')
            array = array_field(row, prefix)
            aliases[prefix] = None if array is None else f'a{len(arrays)}'
            if array is not None:
                if array.dtype.hasobject:
                    raise ValueError('object arrays are not a sensor payload')
                arrays[aliases[prefix]] = array
        excluded = {prefix+suffix for prefix in shaped for suffix in ('.values', '.shape')}
        fields = {name: value.tolist() if isinstance(value, np.ndarray) else value
                  for name, value in row.items() if name not in excluded}
        metadata = {'fields': fields, 'array_fields': aliases}
        metadata_name, arrays_name = f'{index:06d}.json', f'{index:06d}.npz'
        buffer = io.BytesIO(); np.savez(buffer, **arrays)
        meta_bytes, array_bytes = encode(metadata), buffer.getvalue()
        # Admission happens before writing either member of this record.
        if used + len(meta_bytes) + len(array_bytes) > remaining_bytes:
            raise ValueError('decoded component exceeds derived working-set capacity')
        rows.append({'key': keys, 'metadata': metadata_name, 'arrays': arrays_name,
                     'metadata_sha256': write(metadata_name, meta_bytes),
                     'arrays_sha256': write(arrays_name, array_bytes)})
    result = {'schema_version': 1, 'component': component, 'scene': scene,
              'source_sha256': source_sha, 'native_schema_sha256': hashlib.sha256(str(native_schema).encode()).hexdigest(),
              'rows': rows, 'output_bytes': used}
    # Manifest bytes are part of the capacity; settle its own decimal byte count.
    while True:
        data = encode(result); total = used + len(data)
        if result['output_bytes'] == total:
            break
        result['output_bytes'] = total
    write('manifest.json', data)
    return result
