"""Contradictory metadata must fail despite unchanged externally verified pins."""
import copy
import json
import hashlib
from pathlib import Path
import pytest
from association.contract import validate_contract


_MOVED_BASELINE_SOURCES = {
    'pipeline/anchor_assignment.py': 'detection/anchor_assignment.py',
    'pipeline/anchor_grid.py': 'detection/anchor_grid.py',
    'pipeline/box_coding.py': 'detection/box_coding.py',
    'pipeline/detector_geometry.py': 'detection/detector_geometry.py',
    'pipeline/detector_loss.py': 'detection/detector_loss.py',
    'pipeline/pillar_detector.py': 'detection/pillar_detector.py',
    'gpu/architecture_followups.py': 'detection/architecture_followups.py',
    'gpu/architecture_variants.py': 'detection/architecture_variants.py',
    'gpu/norm_variants.py': 'detection/norm_variants.py',
    'gpu/scored_proposals_v3.py': 'detection/scored_proposals_v3.py',
    'tier1/catalog.py': 'detection/detector_recipe_catalog.py',
    'tier1/models.py': 'detection/detector_recipe_models.py',
}

_MOVED_ASSOCIATION_SOURCES = {
    'runtime/requirements.lock': 'runtime_requirements.lock',
    'runtime/Dockerfile.cpu': 'runtime_cpu.Dockerfile',
    'runtime/Dockerfile.training': 'runtime_training.Dockerfile',
}


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def document():
    path = Path(__file__).parents[1] / 'research/association41-runtime-admission-20261003a/manifest.json'
    candidate = json.loads(path.read_text())
    baseline = copy.deepcopy(candidate['baseline_source_hashes'])
    for old, new in _MOVED_BASELINE_SOURCES.items():
        baseline[new] = baseline[old]
    candidate['baseline_source_hashes'] = baseline
    candidate['input_hash_preimages']['baseline_sources_sha256'] = copy.deepcopy(baseline)
    candidate['inputs']['baseline_sources_sha256'] = _hash(baseline)
    association = copy.deepcopy(candidate['association_source_hashes'])
    for old, new in _MOVED_ASSOCIATION_SOURCES.items():
        association[new] = association[old]
    candidate['association_source_hashes'] = association
    candidate['input_hash_preimages']['association_sources_sha256'] = copy.deepcopy(association)
    candidate['inputs']['association_sources_sha256'] = _hash(association)
    for key, field in [('initial_model_tensors_sha256', 'initial_model_tensor_sha256')]:
        value = copy.deepcopy(candidate[field])
        candidate['input_hash_preimages'][key] = value
        candidate['inputs'][key] = _hash(value)
    return candidate, copy.deepcopy(candidate['inputs']), copy.deepcopy(candidate['runtime_locks'])


@pytest.mark.parametrize('field', [
    'baseline_source_hashes', 'frame_bindings', 'input_hash_preimages',
    'association_source_hashes', 'initial_model_tensor_sha256',
    'treatment_recipes', 'model_construction_recipe', 'initial_hash_encoding',
])
def test_contradictory_metadata_cannot_inherit_verified_identity(field):
    candidate, inputs, runtime = document()
    candidate[field] = {}
    with pytest.raises(ValueError):
        validate_contract(candidate, inputs=inputs, runtime_locks=runtime)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
