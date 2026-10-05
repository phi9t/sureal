"""Offline native supervision inventory; zero-row shards remain explicit."""
import hashlib
import io
import json
from pathlib import Path
import sys
import numpy as np
import pyarrow.parquet as pq
from PIL import Image


def main():
    path,component,out=Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3])
    f=pq.ParquetFile(path);frames=set();classes={};elements=0
    for batch in f.iter_batches(batch_size=1):
        timestamp=batch.column(batch.schema.get_field_index('key.frame_timestamp_micros'))[0].as_py();frames.add(timestamp)
        if component=='lidar_segmentation':
            arrays=[]
            for ret in [1,2]:
                prefix=f'[LiDARSegmentationLabelComponent].range_image_return{ret}'
                scalar=batch.column(batch.schema.get_field_index(prefix+'.values'))[0]
                if not scalar.is_valid:continue
                shape=batch.column(batch.schema.get_field_index(prefix+'.shape'))[0].as_py()
                array=scalar.values.to_numpy(zero_copy_only=False).reshape(shape)
                if array.shape[-1]!=2:raise ValueError('semantic channel contract')
                arrays.append(array[...,1])
        elif component=='camera_segmentation':
            prefix='[CameraSegmentationLabelComponent]'
            payload=batch.column(batch.schema.get_field_index(prefix+'.panoptic_label'))[0].as_py()
            divisor=batch.column(batch.schema.get_field_index(prefix+'.panoptic_label_divisor'))[0].as_py()
            if divisor<=0:raise ValueError('panoptic divisor')
            arrays=[np.asarray(Image.open(io.BytesIO(payload)))//divisor]
        else:raise ValueError('unknown supervision family')
        for a in arrays:
            if (a<0).any():raise ValueError("negative semantic category")
            ids,counts=np.unique(a,return_counts=True)
            for category,count in zip(ids,counts):classes[str(int(category))]=classes.get(str(int(category)),0)+int(count)
            elements+=a.size
    result={'component':component,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'native_rows':f.metadata.num_rows,
            'labeled_frames':len(frames),'semantic_counts':classes,'elements':elements,'state':'populated' if f.metadata.num_rows else 'empty'}
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='semantic_counts'}))

if __name__=='__main__':main()
