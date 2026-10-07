load("@rules_python//python:defs.bzl", "py_test")

PYTEST_MODULES = [
    "association/test_contract.py",
    "association/test_provenance.py",
]

LEGACY_NATIVE_TOOL_MODULES = []

TORCH_MODULES = [
    "dataset/expanded_batch_observations_test.py",
    "detection/expanded_batch/models_test.py",
    "detection/expanded_batch/point_modules_test.py",
    "detection/expanded_batch/sparse_sets_test.py",
    "detection/sustained_literal_loss_test.py",
    "detection/sustained_loss_test.py",
    "tests/test_camera_interpolation_parity.py",
    "training_execution/audit_sustained_transition_test.py",
    "training_execution/sustained_chunk_reference_test.py",
    "training_execution/sustained_loop_test.py",
    "training_execution/sustained_reference_test.py",
    "training_execution/sustained_state_test.py",
    "training_execution/sustained_worker_guard_test.py",
]

TORCH_CPU_ONLY_MODULES = [
    "training_execution/audit_sustained_transition_test.py",
    "training_execution/sustained_worker_guard_test.py",
]

LIVE_GATE_MODULES = [
    "evaluation/metrics_sustained_v3_test.py",
    "insula/m0_receipt_test.py",
]

KNOWN_FAILURE_MODULES = []

def perception_test_name(src):
    if src == "tools/test_suites.py":
        return "tools_test_suites"
    return src[:-3].replace("/", "__").replace("-", "_")

def _test_tags(src):
    tags = ["perception_unit"]
    if src in TORCH_MODULES:
        tags.append("requires_gpu")
    if src in LIVE_GATE_MODULES:
        tags.append("requires_live_gate")
    if src in LEGACY_NATIVE_TOOL_MODULES:
        tags.extend(["requires_motion_causal_project_binary", "requires_upstream_protoc"])
    if src in KNOWN_FAILURE_MODULES:
        tags.append("known_failure")
    return tags

def perception_py_test(src, data, extra_data = [], deps = []):
    env = {}
    if src in TORCH_CPU_ONLY_MODULES:
        env["CUDA_VISIBLE_DEVICES"] = ""
    args = [src]
    if src in PYTEST_MODULES:
        args = ["--pytest", src]
    py_test(
        name = perception_test_name(src),
        srcs = ["tools/bazel_test_runner.py"],
        args = args,
        data = data + extra_data,
        imports = ["."],
        legacy_create_init = 0,
        main = "tools/bazel_test_runner.py",
        size = "small",
        tags = _test_tags(src),
        env = env,
        deps = deps,
    )
