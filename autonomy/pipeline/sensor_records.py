"""Native Arrow records and exact original-pixel target gathering."""
import numpy as np
import pyarrow.parquet as pq


def array_field(row,prefix):
    values=row[prefix+'.values'];shape=row[prefix+'.shape']
    if values is None:
        if shape is not None:raise ValueError('shape without payload')
        return None
    if shape is None or any(not isinstance(n,int) or n<=0 for n in shape):raise ValueError('invalid shape')
    a=np.asarray(values)
    if a.size!=np.prod(shape):raise ValueError('payload size mismatch')
    return a.reshape(shape)


def align_point_targets(pixels,range_shape,projection,segmentation):
    pixels=np.asarray(pixels)
    if pixels.ndim!=2 or pixels.shape[1]!=2 or not np.issubdtype(pixels.dtype,np.integer):raise ValueError('pixel identities')
    if np.any(pixels<0) or np.any(pixels>=np.array(range_shape)):raise ValueError('pixel bounds')
    result={}
    for name,array,channels in [('camera_projection',projection,6),('segmentation',segmentation,2)]:
        if array is None:result[name]=None;continue
        if array.shape!=(*range_shape,channels):raise ValueError('target shape mismatch')
        result[name]=array[pixels[:,0],pixels[:,1]]
    return result


def select_rows(path,*,timestamps=None):
    """Stream native rows, selecting frame timestamps without sensor joins."""
    for batch in pq.ParquetFile(path).iter_batches(batch_size=1):
        if timestamps is not None and batch.column(batch.schema.get_field_index('key.frame_timestamp_micros'))[0].as_py() not in timestamps:continue
        row={}
        for name in batch.schema.names:
            scalar=batch.column(batch.schema.get_field_index(name))[0]
            row[name]=scalar.values.to_numpy(zero_copy_only=False) if name.endswith('.values') and scalar.is_valid else scalar.as_py()
        yield row

class OrderedLookup:
    """Bounded native-key cursor; preserves repeated lookups and sparse absence."""
    def __init__(self,rows):
        self.rows=iter(rows);self.current=None;self.last_query=None;self.last_source=None
        self._advance()

    @staticmethod
    def key(row):return (row['key.frame_timestamp_micros'],row['key.laser_name'])

    def _advance(self):
        self.current=next(self.rows,None)
        if self.current is not None:
            key=self.key(self.current)
            if self.last_source is not None and key<=self.last_source:raise ValueError('unordered or duplicate native keys')
            self.last_source=key

    def get(self,key):
        if self.last_query is not None and key<self.last_query:raise ValueError('backward native lookup')
        self.last_query=key
        while self.current is not None and self.key(self.current)<key:self._advance()
        return self.current if self.current is not None and self.key(self.current)==key else None
