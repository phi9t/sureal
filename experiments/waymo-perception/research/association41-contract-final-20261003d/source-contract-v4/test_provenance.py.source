"""Contradictory metadata must fail despite unchanged externally verified pins."""
import copy
import json
import hashlib
from pathlib import Path
import pytest
from association.contract import validate_contract


def document():
    path = Path(__file__).parents[1] / 'research/association41-runtime-admission-20261003a/manifest.json'
    candidate = json.loads(path.read_text())
    for key, field in [('association_sources_sha256', 'association_source_hashes'),
                       ('initial_model_tensors_sha256', 'initial_model_tensor_sha256')]:
        value = copy.deepcopy(candidate[field])
        candidate['input_hash_preimages'][key] = value
        candidate['inputs'][key] = hashlib.sha256(json.dumps(value, sort_keys=True,
            separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
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
