"""Read the Waystone slice receipt and stream native Parquet rows grouped by frame."""
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


class SliceReceipt:
    def __init__(self, slice_dir):
        self.dir = Path(slice_dir)
        self.receipt = json.loads((self.dir / "slice.json").read_text())
        self.slice_id = self.receipt["slice_id"]
        self.release = self.receipt["release"]
        self.split = self.receipt["split"]
        self.contexts = list(self.receipt["contexts"])
        self.objects = {(o["component"], o["context"]): o for o in self.receipt["objects"]}

    def path(self, component, context):
        obj = self.objects.get((component, context))
        if obj is None:
            return None
        return self.dir / obj["relative_path"]

    def sha256(self, component, context):
        obj = self.objects.get((component, context))
        return None if obj is None else obj["sha256"]

    def components(self, context):
        return sorted(c for (c, ctx) in self.objects if ctx == context)


def _row_from_batch(batch):
    row = {}
    for i, name in enumerate(batch.schema.names):
        col = batch.column(i)
        scalar = col[0]
        if name.endswith(".values") and scalar.is_valid:
            row[name] = col.values.to_numpy(zero_copy_only=False) if hasattr(col, "values") else np.asarray(scalar.as_py())
        else:
            row[name] = scalar.as_py()
    return row


def stream_rows(path, columns=None):
    """Yield native rows one at a time in file order; list payloads become NumPy arrays."""
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=1, columns=columns):
        if batch.num_rows == 0:
            continue
        yield _row_from_batch(batch)


def read_rows(path, columns=None):
    return list(stream_rows(path, columns))


class FrameCursor:
    """Group consecutive rows by frame timestamp; frames must be non-decreasing in the file."""

    def __init__(self, path, columns=None, key="key.frame_timestamp_micros"):
        self.rows = stream_rows(path, columns) if path is not None else iter(())
        self.key = key
        self.pending = next(self.rows, None)
        self.last = None
        self.last_query = None

    def get(self, timestamp):
        if self.last_query is not None and timestamp <= self.last_query:
            raise ValueError("frame cursor queried backwards")
        self.last_query = timestamp
        while self.pending is not None and self.pending[self.key] < timestamp:
            self._check_order(self.pending[self.key])
            self.pending = next(self.rows, None)
        group = []
        while self.pending is not None and self.pending[self.key] == timestamp:
            self._check_order(timestamp)
            group.append(self.pending)
            self.pending = next(self.rows, None)
        return group

    def _check_order(self, ts):
        if self.last is not None and ts < self.last:
            raise ValueError("component rows are not grouped by non-decreasing timestamp")
        self.last = ts


def array_field(row, prefix):
    values = row.get(prefix + ".values")
    shape = row.get(prefix + ".shape")
    if values is None:
        if shape is not None:
            raise ValueError("shape without payload for " + prefix)
        return None
    if shape is None or any((not isinstance(n, int)) or n <= 0 for n in shape):
        raise ValueError("invalid shape for " + prefix)
    a = np.asarray(values)
    if a.size != int(np.prod(shape)):
        raise ValueError("payload size mismatch for " + prefix)
    return a.reshape(shape)
