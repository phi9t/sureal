"""Strict readers for per-class score records stored in check.json."""
import math

LEVEL2_CLASS_KEYS = ("1", "2", "3", "4")
SCORE_FIELDS = frozenset({"AP", "APH"})


def _read_score(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("finite bounded native AP/APH required")
    return value


def read_level2_per_class(record):
    if not isinstance(record, dict) or set(record) != set(LEVEL2_CLASS_KEYS):
        raise ValueError("all four native classes required")
    parsed = {}
    for class_key in LEVEL2_CLASS_KEYS:
        row = record[class_key]
        if not isinstance(row, dict) or set(row) != SCORE_FIELDS:
            raise ValueError("complete native AP/APH scores required")
        parsed[class_key] = {field: _read_score(row[field]) for field in ("AP", "APH")}
    return parsed
