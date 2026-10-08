import base64
import hashlib
import json

import pyarrow as pa
import pyarrow.parquet as pq


def native_range_shape_fixture(path):
    row = {
        'key.segment_context_name': 'scene',
        'key.frame_timestamp_micros': 10,
        'key.laser_name': 1,
        '[LiDARComponent].range_image_return1.shape': [64, 2650, 4],
        '[LiDARComponent].range_image_return2.shape': None,
        '[LiDARComponent].range_image_return1.values': [1., 2., 3., 4.],
    }
    pq.write_table(pa.Table.from_pylist([row]), path)
    data = path.read_bytes()
    source = {
        'size_bytes': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'md5_base64': base64.b64encode(hashlib.md5(data).digest()).decode(),
    }
    keys = {key: row[key] for key in row if key.startswith('key.')}
    inventory = {
        'rows': 1,
        'key_sha256': hashlib.sha256(
            (json.dumps(keys, sort_keys=True, separators=(',', ':')) + '\n').encode()
        ).hexdigest(),
    }
    return source, inventory
