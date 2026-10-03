"""Prepare native ground-truth box replay for evaluator verification only."""
from pathlib import Path
import hashlib,json
import pyarrow.parquet as pq

root=Path('/source/raw/validation/lidar_box');records=[];sources={};seen=set()
for p in sorted(root.glob('*.parquet')):
    sources[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    for batch in pq.ParquetFile(p).iter_batches(batch_size=128):
        for row in batch.to_pylist():
            prefix='[LiDARBoxComponent].'
            record={'context_name':row['key.segment_context_name'],'frame_timestamp_micros':row['key.frame_timestamp_micros'],'object_id':row['key.laser_object_id'],'type':row[prefix+'type'],
                    'box':[row[prefix+'box.'+field] for field in ['center.x','center.y','center.z','size.x','size.y','size.z','heading']],
                    'num_lidar_points_in_box':row[prefix+'num_lidar_points_in_box'],'difficulty':row[prefix+'difficulty_level.detection'],
                    'score':1.,'overlap_with_nlz':False}
            key=(record['context_name'],record['frame_timestamp_micros'],record['object_id']);assert key not in seen;seen.add(key)
            records.append(record)
assert len(sources)==2 and len(records)>0
Path('/outputs/real-boxes.json').write_text(json.dumps(records)+'\n')
Path('/outputs/real-box-coverage.json').write_text(json.dumps({'source_hashes':sources,'objects':len(records),'frames':len({(r['context_name'],r['frame_timestamp_micros']) for r in records}),'nonpositive_point_boxes':sum(r['num_lidar_points_in_box']<=0 for r in records),'scope':'ground-truth self-replay only; NLZ false is fixture setting, not a derived prediction-overlap claim'},indent=2)+'\n')
print('Prepared',len(records),'native boxes')
