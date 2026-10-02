"""Admit historical completed checkpoints against externally pinned identities."""
import json
from pathlib import Path
from pipeline.cohort_checkpoint import digest, verify_checkpoint

def verify_registered_checkpoint(path, *, scene, registry,
                                 expected_registry_sha256, **admission):
    if registry is None or expected_registry_sha256 is None:
        raise ValueError('externally trusted checkpoint registry required')
    registry = Path(registry)
    if digest(registry) != expected_registry_sha256:
        raise ValueError('trusted checkpoint registry differs')
    records = json.loads(registry.read_text())
    expected = records.get(scene)
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError('scene absent from trusted checkpoint registry')
    result = verify_checkpoint(path, expected_checkpoint_sha256=expected,
                               **admission)
    if result['scene'] != scene:
        raise ValueError('trusted checkpoint scene differs')
    return result
