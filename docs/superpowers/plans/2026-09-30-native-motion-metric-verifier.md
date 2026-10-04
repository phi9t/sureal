# Native Motion Metric Verifier Implementation Plan

> **For agentic workers:** Use the existing isolated waymo-tracer worktree. Follow test-driven verification; do not commit or alter the verified Perception metric runtime.

**Goal:** Establish independent live execution of the pinned TensorFlow-free native Motion metric regression suites as preparation for ticket 19.

**Architecture:** Add a separate motion-evaluation recipe extending the immutable existing native metric image. Compile only pinned Motion metric units plus geometry/status and generated protos. Export a separate content-locked root and run upstream tests offline using the existing Insula launcher.

**Tech stack:** C++17, CMake, Protobuf, Abseil, glog, GTest; Python host orchestration; no TensorFlow.

## Task 1 — Native upstream regression runtime

Files: create `experiments/waymo-perception/motion-evaluation/{CMakeLists.txt,Dockerfile}` and `verify-motion-native.py`; reuse the existing pinned `/upstream` and `/generated` trees from the immutable Perception image. Preserve `evaluation/*` and `metrics-rootfs`.

1. Observe live failure of the required Motion metric binary in the existing runtime; keep failed evidence.
2. Add separate `motion_metrics_test` and `motion_metrics_utils_test` targets from WOD commit 99a4cb3ff07e2fe06c2ce73da001f850f628e45a. Native sources are motion_metrics.cc, motion_metrics_utils.cc, common/status.cc and math box2d/polygon2d/segment2d; link generated proto library and declared external dependencies.
3. Build against immutable parent image; capture build recipe hashes and image identity. Verify source revision identity remains pinned.
4. Export image to a new motion-metrics-rootfs, compute content identity, store immutable lock including parent image, source revision and recipe hashes.
5. Run both unchanged upstream regression binaries in separate offline live Insula invocations, producing GTest JSON. Require positive test counts, zero failures, zero disabled tests and zero skips. Independently parse per-test statuses.
6. Prove TensorFlow is unavailable and native executable shared-library closures contain no TensorFlow. Record exact commands, UTC interval, root/candidate/output hashes and measured resources.

Acceptance: current candidate-specific successful live receipts and independently checked GTest results for both suites. This is native regression readiness only; it cannot close ticket 19 or establish forecasting evaluation on acquired scenarios.

## Task 2 — Remaining ticket 19 work

Implement explicit native CLI/export and analytic fixtures according to `research/motion-native-evaluator-contract.md`: future-only sample count, first serialized K, confidence semantics, endpoint bounds, missing measurements, malformed inputs and causal feature rejection. Acquire generation-pinned native Scenario and supported sensor extensions through the shared bounded Waystone source policy, with original scenario IDs; camera tokens remain tokens. Independent native fixture parity, actual scenario ingestion and temporal/source reconciliation must pass live before ticket 19 closes. No model training occurs in either task.

## Native CLI first analytic boundary

Files: create `motion-evaluation/cli/{Dockerfile,CMakeLists.txt,motion_metrics_main.cc}`, `tests/test_motion_native_cli.py`, and a separate CLI runtime verifier. Preserve the prior Motion regression runtime/recipe. CLI interface is `compute_motion_metrics SCENARIO.textproto PREDICTIONS.textproto CONFIG.textproto OUTPUT.json`; input files are bounded to 64 MiB. Output includes native metrics and per-class/per-horizon measurement counts, so absent supervision is not mistaken for perfect error. Refuse malformed inputs, source identity mismatch, invalid sampling/current index, endpoint outside future prediction length, duplicate track IDs, invalid prediction shapes/nonfinite values/negative scores. Write no output until scoring succeeds; refuse existing output. First fixtures pin perfect/2m-offset error/counts, first serialized K semantics and fail-before-output for malformed/identity/endpoints. Follow with missing-validity, joint mode and score fixtures before broader adoption. This command is initially single-scenario; pooled native accumulation/export must be separately verified before full-cohort scoring.
