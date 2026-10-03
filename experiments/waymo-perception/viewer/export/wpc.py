"""WPC1: little-endian planar point container, one file per frame.

Header (32 bytes): magic "WPC1", u16 version, u16 header bytes, u32 frame index,
u32 section count, f32 xyz scale (m), u32 reserved, u64 frame timestamp (us).
Section table (32 bytes each, sorted by sensor, return, kind): u8 sensor,
u8 return, u8 kind, u8 dtype, u8 components, 3 pad, u32 point count,
u32 pad, u64 byte offset, u64 byte length. Payloads are 4-byte aligned.
"""
import struct
from collections import namedtuple

import numpy as np

from .constants import DTYPE_F32, DTYPE_I16, DTYPE_I32, DTYPE_U8, DTYPE_U16

MAGIC = b"WPC1"
VERSION = 1
HEADER = struct.Struct("<4sHHIIfIQ")
ENTRY = struct.Struct("<BBBBBxxxIIQQ")
assert HEADER.size == 32 and ENTRY.size == 32

Section = namedtuple("Section", "sensor return_index kind array")

_DTYPES = {
    DTYPE_U8: np.dtype("<u1"), DTYPE_I16: np.dtype("<i2"), DTYPE_U16: np.dtype("<u2"),
    DTYPE_I32: np.dtype("<i4"), DTYPE_F32: np.dtype("<f4"),
}
_CODES = {v: k for k, v in _DTYPES.items()}


def _dtype_code(array):
    dt = np.dtype(array.dtype).newbyteorder("<")
    if dt not in _CODES:
        raise ValueError("unsupported section dtype " + str(array.dtype))
    return _CODES[dt], dt


def write_wpc(path, frame_index, timestamp_micros, xyz_scale, sections):
    sections = sorted(sections, key=lambda s: (s.sensor, s.return_index, s.kind))
    keys = [(s.sensor, s.return_index, s.kind) for s in sections]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate section")
    entries = []
    payload = bytearray()
    base = HEADER.size + ENTRY.size * len(sections)
    for s in sections:
        arr = np.ascontiguousarray(s.array)
        if arr.ndim == 1:
            comps, count = 1, arr.shape[0]
        elif arr.ndim == 2:
            count, comps = arr.shape
        else:
            raise ValueError("section arrays must be 1-D or 2-D")
        code, dt = _dtype_code(arr)
        data = arr.astype(dt, copy=False).tobytes()
        offset = base + len(payload)
        entries.append(ENTRY.pack(s.sensor, s.return_index, s.kind, code, comps, count, 0, offset, len(data)))
        payload += data
        if len(payload) % 4:
            payload += b"\0" * (4 - len(payload) % 4)
    header = HEADER.pack(MAGIC, VERSION, HEADER.size, frame_index, len(sections), float(xyz_scale), 0, int(timestamp_micros))
    blob = header + b"".join(entries) + bytes(payload)
    with open(path, "wb") as f:
        f.write(blob)
    return len(blob)


def read_wpc(path):
    with open(path, "rb") as f:
        blob = f.read()
    magic, version, header_bytes, frame_index, count, scale, _reserved, timestamp = HEADER.unpack_from(blob, 0)
    if magic != MAGIC or version != VERSION or header_bytes != HEADER.size:
        raise ValueError("not a WPC1 file")
    sections = {}
    for i in range(count):
        sensor, ret, kind, code, comps, n, _pad, offset, length = ENTRY.unpack_from(blob, HEADER.size + ENTRY.size * i)
        if offset % 4:
            raise ValueError("misaligned section")
        dt = _DTYPES[code]
        if length != n * comps * dt.itemsize:
            raise ValueError("section length mismatch")
        arr = np.frombuffer(blob, dtype=dt, count=n * comps, offset=offset)
        sections[(sensor, ret, kind)] = arr.reshape(n, comps) if comps > 1 else arr
    header = {"frame_index": frame_index, "timestamp_micros": timestamp, "xyz_scale": scale}
    return header, sections
