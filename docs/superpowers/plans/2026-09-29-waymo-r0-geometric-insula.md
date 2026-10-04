# Waymo R0 Geometric Insula Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** First prove the dedicated CPU Insula works, then replay the verified two-scene data probe inside it and produce trustworthy, identity-preserving point geometry and synchronized sensor inspection artifacts.

**Architecture:** Keep acquisition outside the offline runtime. Stream native Parquet sensor records through an explicit NumPy geometry adapter, retaining original sensor/return/pixel identities. Validate and stage geometry, projection diagnostics and views before immutable promotion; reuse the current native-table tracer without embedding reconstruction into its scanner.

**Tech Stack:** Linux bubblewrap, pinned OCI/rootfs builder, Python 3.12.13, existing hash-locked PyArrow/NumPy/Pillow/jsonschema environment. CPU geometry uses NumPy; learned tensors later use Torch/JAX. No TensorFlow or SDK runtime imports.

**Spec:** `docs/superpowers/specs/2026-09-29-waymo-research-program-design.md`, R0 and information contract. The original pipeline plan remains the broader production roadmap; this plan implements only the next geometric investigation gate.

## Mathematical contract

Read [the geometry foundation](../specs/2026-09-29-perception-geometry-foundation-design.md)
before implementing Tasks 2–4. Use named frame/time and true SE(3) conventions;
add polar singularity, BEV boundary/collision and noncommuting transform fixtures.
Do not substitute SymForce's product-manifold Pose3 update for SE(3) Exp.
Symbolic tooling adoption and generic radar adapters are optional separate
scopes, not prerequisites for reading the acquired LiDAR/camera data.

## Global constraints

- Work in the existing `.worktrees/waymo-tracer` checkout, branch `work/waymo-tracer`; preserve current main-checkout changes.
- No TensorFlow dependencies, SDK imports or evaluator exception.
- HDFS/materialization remain Waystone-owned; reuse `~/.cache/waystone/waymo-perception/slices/validation-two-scenes-20260929` and its receipt. No additional acquisition required.
- Current 397-frame validation cohort is development-only; no training, scientific benchmark or generalization claim.
- Preserve native point key `(context, frame, laser, return, row, column)` and distinguish source indices from compact valid-point indices.
- Exclude NLZ and annotations from observation features; retain them in separately named masks/targets.
- Frame key is scan-start identity, not proof of pose/exposure reference or causal availability.
- Preserve sparse/missing coverage and the 337 unresolved object associations; do not invent labeled-empty supervision or borrow another frame's target.
- No GPU, model download, Motion/E2E adapter, official metric build, new detector or full-release ingestion in R0.

## Review focus

1. Different sensors and returns have different dimensions/coverage; reject mismatches rather than flattening to plausible arrays (Tasks 2–3).
2. Calibration axes, azimuth reversal and extrinsic yaw correction can produce plausible incorrect clouds; independent analytic fixtures must reject them (Task 2).
3. TOP second-return motion compensation shares first-return pixel poses; absent required poses must fail or explicitly mark an uncompensated diagnostic (Task 2).
4. Pixel masks, invalid projections and resizing can silently reorder labels/features; preserve original indices and test hostile permutations (Task 3).
5. A valid namespace flag does not prove offline execution or reproducibility; verify blocked host connection, image identity and replay receipts (Tasks 1, 5).

## Files and seams

All experiment paths below are under `experiments/waymo-perception/`.

| Files | Responsibility |
|---|---|
| `insula/Dockerfile`, `insula/build_rootfs.sh`, `insula/enter_rootfs.sh`, `build.sh`, `enter.sh` | Dedicated CPU image, atomic rootfs materialization, minimal offline mounts |
| `runtime.lock.json`, `tests/test_insula_runtime.py` | Image/package identity and actual runtime isolation |
| `pipeline/geometry.py`, `tests/test_geometry.py` | Pure range reconstruction and rigid reference transforms |
| `pipeline/sensor_records.py`, `tests/test_sensor_records.py` | Projected-column reader, per-return identities and label/projection gathering |
| `pipeline/inspection.py`, `inspect-scene.sh`, `tests/test_inspection.py` | Bounded geometry runner, coverage, views and promotion |
| `geometry-report.schema.json`, `geometry-result.schema.json` | Versioned provenance and output contracts |
| `research/r0-geometric-insula.md`, `research/r0-reproducibility.json`, `README.md` | Real-run evidence and commands |

Use `pipeline/tracer_contracts.py` for source identity/hash/transform contracts
and the existing `tracer.py` for unchanged native-table replay. Do not add heavy
geometry to that scanner. Reference rootfs/mount conventions in
`experiments/photoreal-scenes/insula/` and `experiments/insula-scout/insula/`;
strip their GPU, Blender, driver and exchange mounts. Default R0 to offline.

### Task 1 (M0): Prove the dedicated Insula runtime works

- [ ] Read existing rootfs builders/entrypoints and choose an available OCI builder; pin the selected CPU base by digest, not a mutable tag. Record platform, image digest, build files and normalized environment lock.
- [ ] Add a failing runtime test that starts a host loopback listener, enters the offline runtime and proves that connection cannot succeed. Also test readonly source, writable output, no credential mount and no TensorFlow distribution/import.
- [ ] Implement `build.sh` for networked dependency build and `enter.sh --offline -- command...` for execution. Install the existing `requirements-tracer.lock` with hash verification; no silent host fallback. Rootfs export is staged, validated and atomically promoted.
- [ ] Add `enter.sh --emit-plan` without needing a built rootfs/data. Fail clearly on unavailable builder, wrong rootfs marker or mismatched lock.
- [ ] Run real namespace/filesystem tests and synthetic NumPy, Parquet and image roundtrips through the rootfs. Independently reopen outputs and validate values; no dataset is required for M0.
- [ ] Produce the locked runtime's live M0 receipt and verify it before closing Task 1. Native-table replay is M1 and cannot substitute for runtime boundary checks.

### Task 1b (M1): Replay the acquired native data in verified Insula

- [ ] Require verified M0 and write the source/candidate identity assertions first.
- [ ] Replay full native-table inspection into a fresh run and verify the existing 143,625-row manifest hash `70190074c7d443632523a5c3273d5ead74f4fcddea653addee3a2fa2efa01bcf`, allowing resource metrics to vary.
- [ ] Revalidate all source objects and output lineage independently, then produce the live M1 receipt.
- [ ] Review runtime dependency closure, shell syntax and ShellCheck. Record a missing builder as an environment limitation rather than reporting the existing host-library namespace as completed Insula.

### Task 2: Independently checked range geometry

Interface: `range_to_points(range_image, calibration, *, pixel_pose=None,
frame_pose=None, return_index, motion_policy)` returns an object containing
`xyz_vehicle_reference`, original `(row,column)` indices, physical intensity/
elongation and an explicit reference/motion-policy description. It does not
accept boxes, NLZ, semantics or object IDs as geometry inputs.

- [ ] Read pinned upstream `v2/perception/utils/lidar_utils.py` and range-image utilities without executing them; record upstream commit and exact inclination/azimuth/extrinsic conventions. Do not derive conventions from an attractive plot.
- [ ] Write failing analytic tests for axial rays, explicit versus interpolated inclinations, extrinsic translation/yaw, scan column order, nonidentity frame pose, TOP pixel translation/rotation and first/second-return pose sharing. Expected coordinates come from hand-calculated rays/transforms, not the implementation under test.
- [ ] Implement the minimal NumPy reconstruction: native shape → positive finite range mask → local ray → sensor extrinsic → optional pixel world pose → inverse chosen vehicle reference. Validate rigid transforms and shape consistency before arithmetic.
- [ ] Preserve row-major positive-range ordering, empty-valid arrays and original pixel indices. Return both uncompensated and compensated coordinates only when explicitly requested; never label uncompensated points motion-corrected.
- [ ] Use float64 analytic checks with absolute tolerance `1e-6` m; select and record production output precision after observing real range/error scale. Reject negative/NaN calibration and wrong dimensions. Fail the compensation request if required TOP pixel poses are absent.
- [ ] Run analytic fixtures and deliberate sign/order/return mutations; ensure they fail. Document that ego compensation does not correct actor motion and label-time conventions do not establish exact online acquisition latency.

### Task 3: Sensor identity, semantics and supplied projections

Interface: `iter_sensor_returns(slice_root, selection)` streams one sensor/frame
at a time. Each return contains its complete source key and source hash,
geometry inputs, separately named annotation masks, and supplied projection
records. `gather_by_pixels(array, pixel_indices)` accepts only aligned native
shapes and preserves index order.

- [ ] Write failing Parquet-fixture tests with distinct values on both returns, invalid pixels between valid ones, different sensor widths and sparse missing segmentation. Test a projection/label array with a deliberately wrong shape and swapped point indices.
- [ ] Implement projected-column reads using the existing source receipt checks. Never join large payloads to object tables. Keep labels/calibration/frame metadata at their native grains and sensor names explicit.
- [ ] Gather projection and semantic arrays with the geometry's original pixel indices. Preserve both projection camera slots, reject invalid camera enum/coordinates and record absent/out-of-view states. Instance and semantic IDs remain separate.
- [ ] Separate annotation-unavailable, unlabeled point and labeled point; do not classify absent object rows as an annotated-empty scene. Read TOP pose/label support once and associate returns according to the pinned schema.
- [ ] Verify record conservation: native valid ranges equal emitted points for each sensor/return; all projection/label lengths match; source indices are unique and roundtrip to original pixels. Keep physical features separate from NLZ/targets in tests and output schemas.

### Task 4: Inspectable geometry and synchronization report

Interface: `inspect-scene.sh SAMPLE OUTPUT --selection SELECTION_JSON` runs
offline; `selection` records contexts, frame IDs, sensors, returns, view choices
and reference/motion policy. Defaults scan full geometry but export only a
small declared set of views. Every selected sparse-label view must report why
it was selected; do not imply a label on arbitrary frames.

- [ ] Write failing fixtures for output/source overlap, existing run name, missing required pose, calibration mismatch and injected point/projection permutation. Promotion must not occur on failure.
- [ ] Implement geometry summaries and explicit source/pixel keyed compact point artifacts, with a preflight output estimate and configured byte limit. Stream full-scene geometry without retaining the whole scene in memory.
- [ ] Export a bounded set of calibrated image views with supplied point projections, available point semantics and separately rendered native/projected/synchronized box types; write coordinate-axis point-cloud views and object-history summaries. Never overload box/panoptic identity.
- [ ] Mark image overlays as supplied-projection-based. A simple new pinhole/distortion projection is an independently named timing-approximate diagnostic; report in-bounds counts and pixel residual distributions but do not impose a zero-error requirement across rolling-shutter/moving points. Full camera-model reimplementation is a later capability.
- [ ] Record schema/version, source hashes, source pixel keys, reference transform, temporal assumptions, covered frames/sensors/returns, sparse-label support, unresolved associations, exclusions, output hashes and runtime lock.
- [ ] Validate schemas, source lineage, conservation and artifact hashes before atomic promotion. Independent validation reopens exported points and reconciles identities/counts against source masks. Fail on substituted keys or source hash even after manifest hashes are refreshed.

### Task 5: Real replay, reproducibility and closeout

- [ ] Run the focused geometry/sensor/inspection/runtime suite, the existing 16-test tracer suite, shell checks and whitespace checks. Resolve failures before real-data claims.
- [ ] Run R0 over both existing contexts, all five LiDARs and both returns in the dedicated rootfs. TOP motion compensation must be tested on both returns; report each sensor's actual available pose/label support.
- [ ] Independently validate a fresh run with source receipt revalidation. Repeat identical selection in a second fresh directory. Compare geometry/identity artifacts byte-for-byte when deterministic serialization permits; otherwise specify numerical precision/tolerance and exact identity/hash equality. Resource metrics may differ.
- [ ] Review representative overlays and explicit failure examples: moving actor, return mismatch fixture, sparse segmentation and unresolved association. Quantify coverage and timing assumptions; images alone cannot pass the geometry gate.
- [ ] Write `research/r0-geometric-insula.md` and small reproducibility JSON with commands, input/runtime/code locks, conservation/error summaries, memory/time, output sizes and limitations. Keep raw/generated artifacts in an allowed external cache or workspace staging path; do not write outside writable roots under the current permissions.
- [ ] Update roadmap R0 status only if dedicated isolation, full geometry, identities and report validations pass. Otherwise name the exact unmet gate. R1 training and RSN/SWFormer/camera/R4D implementations remain separate plans.

## Required live gate at the end of every task

Before closing Tasks 1, 1b and 2–5, exercise that task's implementation in the dedicated
live Insula, validate outputs independently and produce the versioned receipt
specified by [the live verification contract](../specs/2026-09-30-live-insula-verification-design.md).
Task 1 (M0) must prove runtime entry, isolation and synthetic IO/computation first. Task 1b (M1) then proves native-table replay. Task 2
must execute analytic and manifold finite-difference fixtures. Task 3 must
exercise real Parquet return/projection/label identities and hostile fixtures.
Task 4 must generate and validate representative real-data views/artifacts.
Task 5 must replay the complete selected cohort twice and reconcile results.

A host-only passing test leaves the task implemented-awaiting-live-verification.
Check Docker/bubblewrap availability again under the current permission profile.
Do not close Task 1 or substitute the existing host-library namespace for the
rootfs requirement. Dependent work may be prepared, but its completion and
scientific claims remain gated by verified prerequisites.

## Completion criterion

The output is a reviewable two-scene sensor-to-scene inspection with verified
geometry, modality coverage and lineage inside a dedicated locked Insula.
It is not a model, metric-parity result or faithful reproduction of any selected
paper. Execute this plan inline, task by task, once its concrete scope is reviewed.

## Execution checkpoint — 2026-09-29

See [execution ledger](../../../experiments/waymo-perception/research/r0-execution-ledger.md).
The tested float64 geometry core is implemented. Task 1 is blocked by managed
Docker/bubblewrap restrictions. Native source adapters and geometric replay
remain incomplete; no task completion boxes have been inferred from the core.
