"""Lossy encodings used by the .wpc container, with exact inverses for verification."""
import numpy as np

from .constants import FLAG_HAS_PROJ, FLAG_NLZ, FLAG_RETURN2, FLAG_SENSOR_SHIFT, XYZ_SCALE_M


def quantize_xyz(xyz, scale=XYZ_SCALE_M):
    q = np.rint(np.asarray(xyz, dtype=np.float64) / scale)
    if q.size and (np.abs(q) > 32767).any():
        raise ValueError("point outside int16 quantization range")
    return q.astype(np.int16)


def dequantize_xyz(q, scale=XYZ_SCALE_M):
    return np.asarray(q, dtype=np.float64) * scale


def encode_intensity(values, cap):
    v = np.clip(np.asarray(values, dtype=np.float64), 0.0, cap)
    return np.rint(255.0 * np.log1p(v) / np.log1p(cap)).astype(np.uint8)


def decode_intensity(codes, cap):
    return np.expm1(np.asarray(codes, dtype=np.float64) / 255.0 * np.log1p(cap))


def encode_elongation(values, maximum):
    v = np.clip(np.asarray(values, dtype=np.float64) / maximum, 0.0, 1.0)
    return np.rint(255.0 * v).astype(np.uint8)


def decode_elongation(codes, maximum):
    return np.asarray(codes, dtype=np.float64) / 255.0 * maximum


def pack_flags(nlz, return_index, sensor, has_proj):
    nlz = np.asarray(nlz, dtype=bool)
    has_proj = np.asarray(has_proj, dtype=bool)
    if return_index not in (1, 2) or not (1 <= sensor <= 7):
        raise ValueError("invalid return index or sensor id")
    flags = np.full(nlz.shape, sensor << FLAG_SENSOR_SHIFT, dtype=np.uint8)
    flags |= nlz.astype(np.uint8) * FLAG_NLZ
    if return_index == 2:
        flags |= FLAG_RETURN2
    flags |= has_proj.astype(np.uint8) * FLAG_HAS_PROJ
    return flags


def unpack_flags(flags):
    f = np.asarray(flags, dtype=np.uint8)
    return {
        "nlz": (f & FLAG_NLZ) != 0,
        "return_index": np.where((f & FLAG_RETURN2) != 0, 2, 1),
        "sensor": (f >> FLAG_SENSOR_SHIFT) & 7,
        "has_proj": (f & FLAG_HAS_PROJ) != 0,
    }
