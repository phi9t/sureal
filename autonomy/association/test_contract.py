"""Contract tests: prevent changed scientific scope and unadmitted execution."""

import copy
import pytest
from association.contract import validate_contract, prediction_alpha
from association.test_provenance import document


def fixture():
    return document()


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("inputs", "frames_sha256", "f" * 64),
        ("inputs", "native_gt_sha256", "f" * 64),
        ("inputs", "eligible_count", 1023),
        ("inputs", "native_count", 1053),
        ("inputs", "fixed_eligible_count", 72),
        ("budgets", "step_seconds", 7201),
        ("budgets", "scientific_bytes", 17179869184),
        ("model", "decoder", "V2"),
        ("graph", "max_radius", 4),
        ("fit", "consecutive", 1),
    ],
)
def test_contract_rejects_changed_frames_gt_sources_and_budgets(section, key, value):
    candidate, inputs, runtime = fixture()
    candidate[section][key] = value
    with pytest.raises(ValueError):
        validate_contract(candidate, inputs=inputs, runtime_locks=runtime)


@pytest.mark.parametrize(
    "step,want", [(0, 0.0), (64, 0.0), (65, 1 / 192), (160, 0.5), (255, 191 / 192), (256, 1.0), (10000, 1.0)]
)
def test_alpha_boundaries(step, want):
    assert prediction_alpha(step) == want


@pytest.mark.parametrize("step", [-1, 1.5, True, "64", None])
def test_alpha_rejects_invalid_completed_updates(step):
    with pytest.raises(ValueError):
        prediction_alpha(step)


@pytest.mark.parametrize(
    "role,key,value",
    [("cpu", "scipy_version", None), ("training", "solver", None), ("training", "admission_sha256", None)],
)
def test_absent_solver_requires_new_runtime_admission(role, key, value):
    candidate, inputs, runtime = fixture()
    runtime[role][key] = value
    candidate["runtime_locks"] = copy.deepcopy(runtime)
    with pytest.raises(ValueError):
        validate_contract(candidate, inputs=inputs, runtime_locks=runtime)


def test_validated_copy_cannot_mutate_caller_or_accepted_pins():
    candidate, inputs, runtime = fixture()
    admitted = validate_contract(candidate, inputs=inputs, runtime_locks=runtime)
    admitted["inputs"]["class_counts"][0] = 0
    assert candidate["inputs"]["class_counts"] == [533, 255, 231, 34]
    assert inputs["class_counts"] == [533, 255, 231, 34]


def test_matching_candidate_and_inputs_cannot_redefine_required_scope():
    candidate, inputs, runtime = fixture()
    inputs["native_count"] = 1053
    candidate["inputs"] = copy.deepcopy(inputs)
    with pytest.raises(ValueError):
        validate_contract(candidate, inputs=inputs, runtime_locks=runtime)


@pytest.mark.parametrize("field", ["focal_alpha", "focal_gamma", "smooth_l1_beta", "direction"])
def test_loss_equations_cannot_drift(field):
    candidate, inputs, runtime = fixture()
    candidate["loss"][field] = "changed"
    with pytest.raises(ValueError):
        validate_contract(candidate, inputs=inputs, runtime_locks=runtime)


def test_primary_ceiling_is_part_of_the_accepted_fixed_batch_protocol():
    candidate, inputs, runtime = fixture()
    candidate["budgets"]["fixed_primary_updates"] = 2000
    assert (
        validate_contract(candidate, inputs=inputs, runtime_locks=runtime)["budgets"]["fixed_primary_updates"] == 2000
    )
    candidate["budgets"]["fixed_primary_updates"] = 3000
    with pytest.raises(ValueError):
        validate_contract(candidate, inputs=inputs, runtime_locks=runtime)


def test_alpha_saturates_without_integer_to_float_overflow():
    assert prediction_alpha(10**1000) == 1.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
