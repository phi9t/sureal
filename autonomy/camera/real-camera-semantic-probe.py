"""Native PNG/class/coverage diagnostic verification; no model inference."""
import io,json,time,resource
from pathlib import Path
from evidence.source_snapshot import file_sha256
import numpy as np
import pyarrow.parquet as pq
from PIL import Image
from segmentation.camera_semantic_scoring import score

root=Path('/source/raw/validation');camera_keys=set();label_keys=set();rows=[];hashes={};started=time.monotonic();eligible=0
for path in sorted((root/'camera_image').glob('*.parquet')):
    for batch in pq.ParquetFile(path).iter_batches(batch_size=128,columns=['key.segment_context_name','key.frame_timestamp_micros','key.camera_name']):
        for row in batch.to_pylist():
            key=(row['key.segment_context_name'],row['key.frame_timestamp_micros'],row['key.camera_name']);assert key not in camera_keys;camera_keys.add(key)
for path in sorted((root/'camera_segmentation').glob('*.parquet')):
    hashes[path.name]=file_sha256(path)
    for batch in pq.ParquetFile(path).iter_batches(batch_size=1):
        row=batch.to_pylist()[0];key=(row['key.segment_context_name'],row['key.frame_timestamp_micros'],row['key.camera_name']);assert key in camera_keys and key not in label_keys;label_keys.add(key)
        p='[CameraSegmentationLabelComponent].';divisor=row[p+'panoptic_label_divisor'];assert type(divisor) is int and divisor>0
        semantic=np.asarray(Image.open(io.BytesIO(row[p+'panoptic_label'])))//divisor
        diagnostic=score(semantic,semantic,np.ones(semantic.shape,dtype=bool))
        expected=int(np.count_nonzero(semantic));assert diagnostic['eligible_pixels']==expected
        if expected:assert diagnostic['mean_iou']==1.
        eligible+=expected
        rows.append({'context':key[0],'timestamp':key[1],'camera':key[2],'shape':list(semantic.shape),'eligible_pixels':expected,'classes_in_mean':diagnostic.get('classes_in_mean',[]),'coverage':diagnostic['coverage']})
assert len(camera_keys)==1985 and len(label_keys)==990
report={'source_hashes':hashes,'camera_observations':len(camera_keys),'annotated_images':len(label_keys),'missing_annotation_images':len(camera_keys-label_keys),'eligible_pixels':eligible,'annotated_no_eligible_images':sum(r['eligible_pixels']==0 for r in rows),'rows':rows,'elapsed_seconds':time.monotonic()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'native camera semantic diagnostic self-replay; official panoptic/STQ not claimed'}
Path('/outputs/camera-report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS real camera semantic coverage',len(rows),eligible)
