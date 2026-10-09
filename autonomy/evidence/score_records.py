"""Strict readers for per-class score records stored in check.json."""
import math

LEVEL2_CLASS_KEYS = ("1", "2", "3", "4")
SCORE_FIELDS = frozenset({"AP", "APH"})


def _read_score(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("finite bounded native AP/APH required")
    return value


def _read_classes(classes):
    if isinstance(classes, (str, bytes)):
        raise ValueError("explicit native classes required")
    try:
        keys = tuple(classes)
    except TypeError as error:
        raise ValueError("explicit native classes required") from error
    if not keys or any(not isinstance(key, str) or not key for key in keys) or len(set(keys)) != len(keys):
        raise ValueError("explicit native classes required")
    return keys


def populated_level2_classes(record):
    try:
        counts = record["groundtruth_by_class"]
    except (KeyError, TypeError) as error:
        raise ValueError("native groundtruth class counts required") from error
    if not isinstance(counts, dict):
        raise ValueError("native groundtruth class counts required")
    parsed = {}
    for raw_key, count in counts.items():
        key = str(raw_key)
        if key not in LEVEL2_CLASS_KEYS or key in parsed or type(count) is not int or count < 0:
            raise ValueError("native groundtruth class counts required")
        parsed[key] = count
    if set(parsed) != set(LEVEL2_CLASS_KEYS):
        raise ValueError("native groundtruth class counts required")
    classes = tuple(key for key in LEVEL2_CLASS_KEYS if parsed[key] > 0)
    if not classes:
        raise ValueError("populated native classes required")
    return classes


def read_level2_per_class(record, *, classes):
    class_keys = _read_classes(classes)
    if not isinstance(record, dict) or set(record) != set(class_keys):
        raise ValueError("expected native class set required")
    parsed = {}
    for class_key in class_keys:
        row = record[class_key]
        if not isinstance(row, dict) or set(row) != SCORE_FIELDS:
            raise ValueError("complete native AP/APH scores required")
        parsed[class_key] = {field: _read_score(row[field]) for field in ("AP", "APH")}
    return parsed
