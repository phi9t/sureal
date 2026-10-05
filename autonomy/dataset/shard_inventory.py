"""Offline native key-only inventory; sensor payload columns are not loaded."""
import hashlib,json
from pathlib import Path
import sys
import pyarrow.parquet as pq


def main():
    path,context,out=Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3]);table=pq.ParquetFile(path)
    columns=[c for c in table.schema_arrow.names if c.startswith('key.')]
    if 'key.segment_context_name' not in columns:raise ValueError('native context absent')
    digest=hashlib.sha256();seen=set();frames=set();count=0
    for batch in table.iter_batches(batch_size=1024,columns=columns):
        for row in batch.to_pylist():
            if row['key.segment_context_name']!=context:raise ValueError('incorrect source segment')
            text=json.dumps(row,sort_keys=True,separators=(',',':'))
            if text in seen:raise ValueError('duplicate native component identity')
            seen.add(text);digest.update((text+'\n').encode());count+=1
            if 'key.frame_timestamp_micros' in row:
                stamp=row['key.frame_timestamp_micros']
                if type(stamp) is not int or stamp<0:raise ValueError('invalid native timestamp')
                frames.add(stamp)
    report={'rows':count,'key_columns':columns,'key_sha256':digest.hexdigest(),'frame_timestamps':sorted(frames),'schema_sha256':hashlib.sha256(str(table.schema_arrow).encode()).hexdigest(),'scope':'native key-only inventory; supervision coverage audited separately'}
    out.write_text(json.dumps(report,indent=2)+'\n');print('PASS native shard inventory',count)

if __name__=='__main__':main()
