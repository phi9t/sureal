"""Independent native panoptic payload and camera coverage reconciliation."""
import hashlib,io,json
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from PIL import Image

root=Path('/source/raw/validation');report=json.loads(Path('/opt/camera-report.json').read_text())
expected={(r['context'],r['timestamp'],r['camera']):r for r in report['rows']};seen=set();eligible=0
for path in sorted((root/'camera_segmentation').glob('*.parquet')):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==report['source_hashes'][path.name]
    for batch in pq.ParquetFile(path).iter_batches(batch_size=1):
        row=batch.to_pylist()[0];key=(row['key.segment_context_name'],row['key.frame_timestamp_micros'],row['key.camera_name'])
        assert key in expected and key not in seen;seen.add(key)
        prefix='[CameraSegmentationLabelComponent].';divisor=row[prefix+'panoptic_label_divisor']
        panoptic=np.asarray(Image.open(io.BytesIO(row[prefix+'panoptic_label'])));assert panoptic.ndim==2 and divisor>0
        # Independent threshold count: semantic ID zero iff panoptic < divisor.
        supported=int(np.sum(panoptic>=divisor));assert supported==expected[key]['eligible_pixels']
        assert list(panoptic.shape)==expected[key]['shape']
        ids=np.unique(np.floor_divide(panoptic,divisor));assert np.all((ids>=0)&(ids<=28))
        assert [int(i) for i in ids if i!=0]==expected[key]['classes_in_mean']
        eligible+=supported
observed=set()
for path in sorted((root/'camera_image').glob('*.parquet')):
    for batch in pq.ParquetFile(path).iter_batches(batch_size=512,columns=['key.segment_context_name','key.frame_timestamp_micros','key.camera_name']):
        for row in batch.to_pylist():
            key=(row['key.segment_context_name'],row['key.frame_timestamp_micros'],row['key.camera_name']);assert key not in observed;observed.add(key)
assert seen==set(expected) and seen<=observed
assert len(observed)==report['camera_observations']==1985
assert len(observed-seen)==report['missing_annotation_images']==995
assert eligible==report['eligible_pixels']==2133338748
Path('/outputs/source-validation.json').write_text(json.dumps({'annotated_images':len(seen),'missing_annotations':len(observed-seen),'eligible_pixels':eligible,'status':'native camera keys, payload dimensions, native classes and support counts independently reconciled'},indent=2)+'\n')
print('PASS independent camera source',len(seen),eligible)
