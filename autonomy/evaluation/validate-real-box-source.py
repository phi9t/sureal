"""Independent exact native Parquet row reconciliation for detection replay."""
from pathlib import Path
import hashlib,json
import pyarrow.parquet as pq

records=json.loads(Path('/opt/real-boxes.json').read_text())
expected={(r['context_name'],r['frame_timestamp_micros'],r['object_id']):r for r in records}
assert len(expected)==len(records)==38363
seen=set();counts={}
for path in sorted(Path('/source/raw/validation/lidar_box').glob('*.parquet')):
    counts[path.name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':0}
    for batch in pq.ParquetFile(path).iter_batches(batch_size=1):
        row=batch.to_pylist()[0];key=(row['key.segment_context_name'],row['key.frame_timestamp_micros'],row['key.laser_object_id'])
        assert key not in seen and key in expected;seen.add(key);record=expected[key]
        p='[LiDARBoxComponent].'
        actual=[row[p+'box.'+field] for field in ['center.x','center.y','center.z','size.x','size.y','size.z','heading']]
        assert record['box']==actual
        assert record['type']==row[p+'type']
        assert record['num_lidar_points_in_box']==row[p+'num_lidar_points_in_box']
        assert record['difficulty']==row[p+'difficulty_level.detection']
        counts[path.name]['rows']+=1
assert seen==set(expected)
Path('/outputs/source-validation.json').write_text(json.dumps({'objects':len(seen),'source_files':counts,'status':'all native detection identities/geometry/metadata reconciled','scope':'evaluator replay, no production NLZ inference'},indent=2)+'\n')
print('PASS independent native box source',len(seen))
