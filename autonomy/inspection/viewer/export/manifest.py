"""Deterministic JSON and hashing helpers."""
import hashlib
import json
from pathlib import Path

import numpy as np
from evidence.source_snapshot import file_sha256 as sha256_file


def canonical_json(value):
    """UTF-8 JSON bytes with sorted keys, compact separators and no NaN."""
    return (json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _plain(value):
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_plain(v) for v in value.tolist()]
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and not np.isfinite(value):
        raise ValueError("non-finite float in manifest")
    return value


def dump_json(value, path):
    data = canonical_json(value)
    Path(path).write_bytes(data)
    return data


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def mat4(values):
    """Row-major 16-list -> (4,4) float64 array, validated as a rigid transform."""
    m = np.asarray(values, dtype=np.float64).reshape(4, 4)
    if not np.isfinite(m).all():
        raise ValueError("non-finite transform")
    if not np.allclose(m[3], [0, 0, 0, 1], atol=1e-9):
        raise ValueError("transform is not homogeneous")
    r = m[:3, :3]
    if not np.allclose(r @ r.T, np.eye(3), atol=1e-6) or abs(np.linalg.det(r) - 1) > 1e-6:
        raise ValueError("transform rotation is not proper orthonormal")
    return m


def mat4_list(m):
    return [float(v) for v in np.asarray(m, dtype=np.float64).reshape(16)]


def inverse_rigid(m):
    r = m[:3, :3]
    t = m[:3, 3]
    out = np.eye(4)
    out[:3, :3] = r.T
    out[:3, 3] = -r.T @ t
    return out
