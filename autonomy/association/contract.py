"""Frozen ticket41 protocol; callers supply independently verified input/receipt pins.

This validates identity and policy, not the authenticity of a receipt. Admission
must additionally replay/re-hash the referenced evidence in live Insula.
"""
import copy
import hashlib
import json
import re
from pathlib import PurePosixPath

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_POLICY = {
    "schema_version": 1,
    "treatments": ["A0", "A1", "A2", "A3"],
    "graph": {"initial_radius": 1, "max_radius": 3, "slots_per_cell": 8,
              "expansion": "deficient_components", "legacy_exceptions": True},
    "optimizer": {"name": "Adam", "lr": 1e-4, "betas": [0.9, 0.999],
                  "eps": 1e-8, "weight_decay": 0, "foreach": False, "clip": 10},
    "model": {"seed": 17, "bev_norm": "GN8", "pillar_norm": "BN",
              "dtype": "float32", "tf32": False, "deterministic": True,
              "augmentation": False, "decoder": "correctedV3"},
    "loss": {"focal_alpha": 0.25, "focal_gamma": 2.0, "smooth_l1_beta": 1/9,
             "direction": "canonical_legacy", "localization_weight": 2.0,
             "direction_weight": 0.2, "normalizer": "positive_count"},
    "costs": {"A1": "1-nearestBEVIoU", "A2": [1.0, 1.0],
              "A3": [1.0, 2.0, 0.2, 1.0], "warmup_end": 64, "ramp_end": 256},
    "checkpoints": {
        "fixed": [0,25,50,100,200,300,500,750,1000,1500,2000,3000,4000,6000,8000,10000],
        "balanced16": [0,1000,2000,4000,8000,12000,16000,24000,32000]},
    "budgets": {"gpu_bytes": 8589934592, "rss_bytes": 17179869184,
                "raw_bytes": 2147483648, "scientific_bytes": 16106127360,
                "case_reserve_bytes": 2147483648, "step_seconds": 7200,
                "native_seconds": 14400, "host_seconds": 14700,
                "fixed_primary_updates": 2000, "fixed_updates": 10000, "balanced_updates": 32000},
    "fit": {"classes": [1,2,3,4], "metric": "native_LEVEL2_APH", "threshold": 0.8,
            "consecutive": 2, "terminal_required": True, "confirmation_updates": 1000},
    "model_construction_recipe": {"architecture": "baseline", "norm": "gn_backbone",
        "max_points": 32, "pillar_cap": 20000, "learning_rate": 1e-4,
        "clip": 10.0, "foreground_prior": None, "loss": "reference"},
    "treatment_recipes": {
        "A0": "unchanged legacy matcher",
        "A1": "global reservations using nearestBEVIoU; unchanged unreserved legacy owners",
        "A2": "global reservations using encoded six-residual mean +1-rotated3DIoU",
        "A3": "same-forward detached costs; completed-update alpha schedule"},
    "input_hash_encoding": {"format": "UTF-8 JSON", "sort_keys": True,
        "ensure_ascii": True, "separators": [",", ":"], "algorithm": "sha256"},
    "initial_hash_encoding": "sorted name,dtype,shape compact UTF8JSON + LF followed by contiguous NumPy native bytes",
}
_SCOPE = {"eligible_count": 1053, "native_count": 1279,
          "fixed_eligible_count": 73, "frame_count": 16,
          "class_counts": [533,255,231,34]}
_INPUT_HASHES = ("frames_sha256", "eligible_gt_sha256", "native_gt_sha256",
                 "fixed_frame_sha256", "baseline_sources_sha256",
                 "association_sources_sha256", "initial_model_tensors_sha256")
_BASELINE_REQUIRED = {"tier1/models.py", "tier1/catalog.py",
    "detection/pillar_detector.py", "detection/detector_loss.py", "detection/anchor_grid.py",
    "detection/anchor_assignment.py", "detection/box_coding.py", "detection/detector_geometry.py",
    "gpu/norm_variants.py", "gpu/architecture_variants.py", "gpu/architecture_followups.py",
    "gpu/scored_proposals_v3.py"}
_ASSOCIATION_REQUIRED = {"contract.py", "runtime/requirements.lock",
    "runtime/Dockerfile.cpu", "runtime/Dockerfile.training"}


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("contract must contain finite JSON values") from exc


def _hash(value, name):
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"missing or invalid {name}")


def _source_map(value, required, name):
    if type(value) is not dict or not required.issubset(value):
        raise ValueError(f"incomplete {name}")
    for path, digest in value.items():
        if (not isinstance(path, str) or not path or "\\" in path
                or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts
                or str(PurePosixPath(path)) != path):
            raise ValueError(f"invalid {name} path")
        _hash(digest, name + " " + path)


def _validate_metadata(candidate, inputs):
    """Derive embedded identities; never trust redundant candidate digests."""
    baseline = candidate.get("baseline_source_hashes")
    association = candidate.get("association_source_hashes")
    _source_map(baseline, _BASELINE_REQUIRED, "baseline sources")
    _source_map(association, _ASSOCIATION_REQUIRED, "association sources")
    frames = candidate.get("frame_bindings")
    if type(frames) is not list or len(frames) != 16:
        raise ValueError("exact sixteen frame bindings required")
    identities = set()
    for frame in frames:
        if type(frame) is not dict:
            raise ValueError("frame binding must be a dictionary")
        identity = frame.get("identity")
        if not isinstance(identity, str) or not identity or identity in identities:
            raise ValueError("unique frame identities required")
        identities.add(identity)
        _hash(frame.get("boxes_sha256"), "frame annotation source")
        for field, count in [("native_ids", "native"), ("eligible_ids", "eligible")]:
            ids = frame.get(field)
            if (type(ids) is not list or any(not isinstance(x, str) or not x for x in ids)
                    or len(set(ids)) != len(ids) or type(frame.get(count)) is not int
                    or frame[count] != len(ids)):
                raise ValueError("frame object IDs and counts disagree")
        if not set(frame["eligible_ids"]).issubset(frame["native_ids"]):
            raise ValueError("eligible IDs must belong to full native GT")
    if (sum(f["native"] for f in frames) != 1279
            or sum(f["eligible"] for f in frames) != 1053 or frames[7]["eligible"] != 73):
        raise ValueError("embedded frame scope differs from frozen counts")
    initial = candidate.get("initial_model_tensor_sha256")
    if type(initial) is not dict or set(initial) != {"A0", "A1", "A2", "A3"}:
        raise ValueError("all four initial model tensor identities required")
    for treatment, digest in initial.items():
        _hash(digest, treatment + " initial tensors")
    if len(set(initial.values())) != 1:
        raise ValueError("initial model tensors differ across treatments")
    derived = {"frames_sha256": frames, "fixed_frame_sha256": frames[7],
               "baseline_sources_sha256": baseline, "association_sources_sha256": association,
               "initial_model_tensors_sha256": initial}
    for field, ids in [("native_gt_sha256", "native_ids"), ("eligible_gt_sha256", "eligible_ids")]:
        derived[field] = [{"identity": f["identity"], "ids": sorted(f[ids]),
                          "boxes_sha256": f["boxes_sha256"]} for f in frames]
    if _canonical(candidate.get("input_hash_preimages")) != _canonical(derived):
        raise ValueError("embedded hash preimages contradict frame/source/tensor bindings")
    for field, value in derived.items():
        if hashlib.sha256(_canonical(value).encode()).hexdigest() != inputs[field]:
            raise ValueError(f"embedded identity differs from verified pin: {field}")


def prediction_alpha(completed_updates: int) -> float:
    """Assignment for the next update uses this completed-update cursor."""
    if type(completed_updates) is not int or completed_updates < 0:
        raise ValueError("completed_updates must be a nonnegative integer")
    if completed_updates <= 64:
        return 0.0
    if completed_updates >= 256:
        return 1.0
    return (completed_updates - 64) / 192


def validate_contract(candidate: dict, *, inputs: dict, runtime_locks: dict) -> dict:
    """Reject scope/policy drift; return a deeply isolated validated manifest.

    ``inputs`` and ``runtime_locks`` must come from verified external artifacts,
    never from the candidate itself. SHA strings alone do not admit a runtime.
    """
    if not all(type(x) is dict for x in (candidate, inputs, runtime_locks)):
        raise ValueError("manifest, inputs and runtime locks must be dictionaries")
    _canonical(candidate)
    for key, expected in _POLICY.items():
        if key not in candidate or _canonical(candidate[key]) != _canonical(expected):
            raise ValueError(f"changed study policy: {key}")
    if set(inputs) != set(_INPUT_HASHES) | set(_SCOPE):
        raise ValueError("incomplete or unknown input identities")
    for key in _INPUT_HASHES:
        _hash(inputs[key], key)
    for key, expected in _SCOPE.items():
        if _canonical(inputs[key]) != _canonical(expected):
            raise ValueError(f"changed study scope: {key}")
    if _canonical(candidate.get("inputs")) != _canonical(inputs):
        raise ValueError("candidate input identities differ from verified inputs")
    if set(runtime_locks) != {"cpu", "training"}:
        raise ValueError("both CPU and training runtime admissions are required")
    for role, lock in runtime_locks.items():
        if type(lock) is not dict or set(lock) != {
            "rootfs_sha256", "solver", "scipy_version", "admission_sha256"
        }:
            raise ValueError(f"incomplete runtime identity: {role}")
        _hash(lock["rootfs_sha256"], role + " rootfs")
        _hash(lock["admission_sha256"], role + " admission")
        if lock["solver"] != "scipy.optimize.linear_sum_assignment":
            raise ValueError(f"missing admitted SciPy solver: {role}")
        if not isinstance(lock["scipy_version"], str) or not re.fullmatch(
            r"\d+\.\d+\.\d+", lock["scipy_version"]
        ):
            raise ValueError(f"missing pinned SciPy version: {role}")
    if runtime_locks["cpu"]["scipy_version"] != runtime_locks["training"]["scipy_version"]:
        raise ValueError("solver versions differ across preparation and training")
    if _canonical(candidate.get("runtime_locks")) != _canonical(runtime_locks):
        raise ValueError("candidate runtime identities differ from admissions")
    _validate_metadata(candidate, inputs)
    return copy.deepcopy(candidate)
