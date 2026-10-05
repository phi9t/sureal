# Waymo Perception Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a deterministic, validated scene manifest from a bounded Waymo Perception v2 component bundle, without introducing Waymo dependencies into Surflo.

**Architecture:** A CPU-only experiment reads projected Parquet columns into typed records at their native component grain. An offline Insula runner writes manifests and reports to staging, validates source and output hashes, then promotes an immutable run. HDFS owns the complete selected dataset release; a manifest-selected local slice retains every available component for two complete scenes. Synthetic contract tests precede HDFS-to-local staging, a real-data probe and reduced pilot.

**Tech Stack:** Dedicated Python 3.10 environment, PyArrow for Parquet I/O, JSON Schema validation, standard-library unittest, Bash, Docker/Podman rootfs materialization, bubblewrap isolation. Tensor computation, if subsequently needed, uses Torch and/or JAX. No TensorFlow, Pandas, Dask, or Waymo SDK imports; the initial metadata reader needs no tensor framework or GPU.

**Spec:** [Waymo pipeline design](../specs/2026-09-29-waymo-perception-data-pipeline-design.md).

**Supporting review:** [Source and design review](../../../experiments/waymo-perception/research/design-review.md).

**Status:** Proposed implementation plan; no pipeline implementation or real-data validation performed. Choices below resolve draft ambiguity for review; the HDFS/full-dataset and local/all-modality storage topology is user-specified; concrete paths, byte budgets and dataset access remain unresolved.

## Global Constraints

- Input: dataset version, split, source root or sample file, selected modalities.
- Output: deterministic manifest rows and a validation result.
- Invariants: stable scene/frame/sensor identities, calibrated metric frames, explicit missing/unknown/uncollected states, and no payload redistribution.
- Network is allowed only in explicit build/fetch stages; validation and conversion run offline once data is staged.
- Outputs write to staging, validate schema and hashes, then promote atomically.
- The complete selected dataset lives under HDFS; a bounded, byte-preserving all-modality slice lives under a local cache root, outside git.
- The Waymo SDK must be isolated from the Surflo package baseline.
- User constraint: no TensorFlow, including transitive dependencies, build tools, verification environments, optional fallbacks, or reference execution. Torch and/or JAX are the permitted tensor frameworks; Parquet I/O remains PyArrow.
- Do not accept dataset terms, embed credentials, train a model, mirror the full dataset locally, or claim perception quality from a smoke reader.
- Preserve existing user changes to `README.md` and the untracked Waymo design/experiment files. Commit only the task's intended files during execution.

## Design review and recommended decisions

1. **Keep ownership in Sureal.** Existing `photoreal-scenes` and `3d-pathway` experiments already demonstrate schema validation, source locks, geometry provenance, and cache-backed execution. Reuse their conventions; do not import their Blender/GPU-dependent validators or expand their APIs to accommodate Waymo.
2. **Select v2.0.1 Parquet for the probe.** The spec's SDK constraints apply to an SDK-dependent path, not to generic Parquet inspection. Use Python 3.10 to match this repository's baseline, not because raw v2 reading requires TensorFlow. The user's no-TensorFlow constraint supersedes the draft's SDK fallback: exclude SDK execution entirely. Any later v1 support requires a separate TensorFlow-free reader design; do not implement two readers preemptively.
3. **Select a dedicated CPU Insula.** A venv separates dependencies but does not enforce offline execution. Follow `experiments/photoreal-scenes/insula/enter_rootfs.sh` for network namespaces and mounts, stripping GPU, exchange, and Blender handling. Fail explicitly if isolation is unavailable; do not silently execute on the host.
4. **Use HDFS as the authoritative store and retain two complete scenes locally.** Preserve the full selected release/splits/components in immutable HDFS raw storage. Select local scene contexts from the HDFS inventory by measured modality coverage, copy every available component for each selected context byte-for-byte, and keep all sensors, returns and timestamps. Keep acquisition/staging separate from offline manifest construction. Full upstream-to-HDFS ingestion is a separate acquisition workstream; Waystone owns HDFS-to-local materialization and storage policy; this plan validates and consumes its handoff. Do not reduce the local acquisition to the six components understood by the first reader.
5. **Preserve native row grain.** Calibration is segment/sensor scoped; images, ranges and `stats` are frame scoped (with sensor keys where applicable); 3D labels are frame/object scoped. A flat camera-by-LiDAR-by-object table multiplies rows and misrepresents scene labels as sensor-specific. Emit typed JSONL records with references, and a frame index derived from the union of observed frame keys. This intentionally extends the review's vehicle-pose anchor recommendation: orphan sensor/label timestamps stay visible as invalid/incomplete frames rather than disappearing; a complete frame still requires its vehicle pose.
6. **Separate source availability from validity.** Absent shards, absent frame rows, empty label collections, withheld labels, unsupported components, and malformed data need separate evidence. A missing row alone cannot establish that something was never collected. Record unknown when acquisition/source evidence cannot distinguish those cases.
7. **Preserve geometry before converting it.** Retain upstream transforms, distortion, timing, pose scope, and units. Camera images are distorted observations; LiDAR range-image values are not camera-axis depth. The first release emits scalar range summaries, not motion-compensated world points or undistorted images.
8. **Separate deterministic content from execution metadata.** Manifest content excludes host paths, run IDs, clock times, and resource measurements. Reports retain those measurements and lineage. Compare manifest bytes and hashes across runs, not complete report bytes.

## Human-input gates

Tasks 1–5 are implementable with original synthetic fixtures and no dataset access. Before Task 5a, record the terms/access attestation, Waystone-resolved HDFS root and inventory, local slice root, measured local byte ceiling, and retention policy outside git. Defer concrete paths and budgets to `~/workspace/waystone`; do not invent a Waymo cache setting from its FineWeb-specific cache configuration. Waystone owns HDFS authentication and transfers; Sureal receives local files and provenance without credentials. Default cohort target: two complete scenes from a label-bearing split, selected for complementary component coverage. Download/stage every available modality and all native sensors/frames for those scenes; the first inspection may process only 20 timestamps as a computational smoke limit. That processing limit must never truncate the stored scene files.

Task 7 requires an explicit pilot processing budget. If dashboard setup is needed, use the wizard skill then. A selected pair that exceeds the local byte ceiling must be rejected or replaced by another explicitly manifested pair; do not silently drop components, sensors or timestamps.

## Storage and local slice contract

```text
{hdfs_root}/waymo/perception/{release}/raw/{split}/{component}/{context}.parquet
{hdfs_root}/waymo/perception/{release}/inventories/{inventory_id}.jsonl
{local_cache}/slices/{slice_id}/raw/{split}/{component}/{context}.parquet
{local_cache}/slices/{slice_id}/slice.json
{local_cache}/runs/{run_id}/...
```

These are proposed relative conventions; HDFS root and local slice root come from Waystone’s resolved handoff. Preserve an existing HDFS layout through its inventory instead of moving data merely to match this convention.

“All modalities” means all components available in the selected release for the selected contexts, including images, ranges, calibration, poses, boxes/associations/projections, segmentation, keypoints, statistics and object-asset families wherever collected. The source inventory defines membership; no hardcoded six-component acquisition allowlist. Components keyed by object rather than context filenames must be selected by their source-defined context relationship. Unknown component families are retained and inventoried, with interpretation reported as unsupported until their schema is mapped.

Require a component-by-context coverage matrix that distinguishes present, unavailable upstream, not yet ingested into HDFS, unknown and unsupported interpretation. Prefer two contexts covering the broadest available component union; do not claim every modality occurs in each scene or at every frame. If HDFS lacks a component that the upstream inventory lists for a selected scene, fail local staging as incomplete. If the release omits a capability (for example the existing research describes v2 without maps), report it as outside release scope; cross-release pairing needs a separate lineage design.

The complete HDFS mirror must have its own inventory/completeness evidence; never infer full-dataset completion from a successful two-scene copy. HDFS block checksums and provider checksums are not interchangeable with content SHA-256. Preserve all known checksum algorithms and use matching content digests for byte identity. Local slice metadata records source HDFS URI, inventory ID, release/split/context/component, sizes and digests. Stage locally, verify every expected object, then atomically promote; processing reads the promoted slice offline.

## Review Focus

- Missing component shards or sparse frame rows must retain the union frame index and report availability without silently dropping frames — Task 3.
- Duplicate keys or joins with unexpected multiplicity must fail rather than generate a cross product — Tasks 2–3.
- Mixed contexts, unknown sensor enums, corrupt footers, and nonfinite or invalid transforms must produce specific validation errors — Tasks 2–3.
- Unsafe paths, input mutation, interrupted writes, and concurrent promotion must leave completed runs intact — Task 4.
- Large payload columns must be excluded from metadata scans; selected payload summaries must obey memory and byte ceilings — Tasks 3 and 7.

## File structure and interfaces

All paths below are relative to `experiments/waymo-perception/` unless explicitly stated.

| File | Responsibility |
| --- | --- |
| `recipe.json`, `dataset.lock.json`, `verify_recipe.py` | Execution/source pins and recipe verification; empty real-source inventory initially |
| `manifest.schema.json`, `result.schema.json`, `report.schema.json` | Versioned manifest, run, and diagnostic contracts |
| `pipeline/contracts.py` | Component registry, identity/state rules, canonical JSON, request validation |
| `pipeline/slice.py`, `slice.schema.json` | Validate the Waystone-provided local slice, source lineage and coverage |
| `pipeline/sources.py` | Bounded local discovery, file inventory, Parquet footer/schema and key checks |
| `pipeline/manifest.py` | Projected reads, typed records, frame index and reference validation |
| `pipeline/validator.py` | JSON Schema and semantic/hash validation |
| `pipeline/run_store.py` | Staging, exclusive promotion, immutable run lifecycle |
| `pipeline/cli.py` | CLI dispatch, exit codes, reports and budgets |
| `requirements.in`, `requirements.lock` | Minimal direct dependencies and exact hash-pinned environment |
| `build.sh`, `enter.sh`, `run.sh`, `insula/*` | Build/materialize the rootfs, offline mounts and dispatch |
| `tests/fixtures.py`, `tests/test_*.py` | Original small Parquet fixtures and behavioral tests |

Do not create a package under `surflo/`. Run tests with `PYTHONPATH=experiments/waymo-perception`; import `pipeline.*` only from this experiment.

Shared types in `pipeline/contracts.py`:

- `ProbeRequest`: release, split, component paths, requested sensors, frame limit, input/output byte limits, maximum decoded row-group bytes, and policy path. Release is explicitly `v2.0.1` initially; split is an explicit value, never inferred from a filename. Decoded row-group budget is required for payload summary reads; enforce it conservatively from projected Parquet footer sizes before decoding, with measured process-memory limits in the pilot.
- `SourceEntry`: source ID, component, context, source-relative path, bytes, SHA-256, Arrow schema fingerprint, key grain; optional upstream URI/generation/checksum and HDFS URI/inventory ID/slice ID. Unknown remote provenance remains null, not fabricated.
- `ManifestRecord`: schema version, record kind, release/split/context identity, native key, values/references, source ID, and availability evidence. Its stable ID is SHA-256 of the canonical JSON array `[release, split, component, ...native_key_values]`.
- `ValidationIssue`: code, severity, source ID, key/field location, concise message. No payload or credential content in errors.
- `ValidationReport`: pass/fail, issue list, component/frame counts, availability counts, measured join cardinalities, and schema versions.

Serialization is UTF-8 JSON with sorted keys, compact separators, `allow_nan=False`, and one trailing newline per record. Sort records by `(record_kind, canonical_native_key)` and sort source inventory by `(component, context, source-relative path)`. Timestamp keys remain integer microseconds. Hash source files in bounded chunks; never load a file merely to compute its hash.

## Task 1: Freeze the contract and experiment recipe

**Files:** Create `pipeline/__init__.py`, `pipeline/contracts.py`, the three schemas, `recipe.json`, `dataset.lock.json`, `verify_recipe.py`, `tests/test_contracts.py`. Modify `README.md` and `roadmap.md` only to document chosen/proposed decisions and accurate ticket status.

**Interfaces:** Produces `validate_request(request: ProbeRequest) -> None`, `canonical_json(value: object) -> bytes`, `record_id(release: str, split: str, component: str, key: tuple) -> str`, and the shared types above.

- [ ] Write failing `test_record_id_is_unambiguous_and_stable`, `test_invalid_requests`, and schema examples for segment calibration, frame pose, camera image reference, LiDAR summary, and scene label. Assert release/split changes change IDs, embedded delimiters do not collide, frame timestamps are integers, null differs from zero, and NaN is rejected.
- [ ] Run `PYTHONPATH=experiments/waymo-perception python -m unittest discover -s experiments/waymo-perception/tests -p 'test_contracts.py' -v`; confirm failure from missing implementation.
- [ ] Implement types, registry, schemas, and recipe verifier. Availability enum: `present`, `missing`, `unknown`, `uncollected`, `withheld`, `not_selected`, `unsupported`, `malformed`, `contradictory`; require evidence for `uncollected` and `withheld`. Reject malformed/contradictory required records. Recipe pins upstream commit `99a4cb3ff07e2fe06c2ce73da001f850f628e45a`; source lock has no invented real-data entries.
- [ ] Rerun the focused suite and `python experiments/waymo-perception/verify_recipe.py`; require pass. Review the source-backed registry against the supporting review before coding a field mapping.
- [ ] Commit only Task 1 files: `feat: define Waymo manifest contract`.

## Task 2: Inventory and validate local component bundles

**Files:** Create `pipeline/sources.py`, `tests/fixtures.py`, `tests/test_sources.py`.

**Interfaces:** Consumes Task 1 types. Produces `inventory_sources(request: ProbeRequest) -> list[SourceEntry]` and `validate_source(entry: SourceEntry, request: ProbeRequest) -> list[ValidationIssue]`. Physical convention is `{sample_root}/{component}/{context}.parquet`; a single shard permits only a partial diagnostic probe.

- [ ] Generate original Parquet fixtures with flat upstream-style column names and small binary values. Write failing tests for correct inventories, corrupt footers, missing keys, duplicates at native grain, conflicting path/context, unknown enums, mixed contexts, unsafe symlinks, and a byte ceiling exceeded before a scan.
- [ ] Run the `test_sources.py` unittest discovery command; verify failure.
- [ ] Implement allowlisted local discovery, projected key reads, non-null/unique native-key checks, SHA-256 inventory, and schema fingerprints including relevant Arrow field types. Reject paths resolving outside the declared source root and inputs overlapping outputs. Retain unsupported component entries in inventory and coverage reports; refuse to interpret them as supported manifest records, without dropping their staged raw files. Calibration keys have no frame timestamp; `lidar_box` keys have no `laser_name`.
- [ ] Rerun focused tests; require pass and unchanged input hashes. Test source identifiers remain stable when the same relative bundle moves to another host directory.
- [ ] Commit Task 2 files: `feat: validate bounded Waymo component sources`.

## Task 3: Emit geometry-preserving deterministic manifests

**Files:** Create `pipeline/manifest.py`, `pipeline/validator.py`, `tests/test_manifest.py`, `tests/test_geometry.py`.

**Interfaces:** Consumes verified sources. Produces `build_manifest(request: ProbeRequest, sources: list[SourceEntry], destination: Path) -> ValidationReport` and `validate_manifest(path: Path, sources: list[SourceEntry]) -> ValidationReport`.

- [ ] Write failing tests for byte-identical manifests from shuffled source rows; union frame discovery when a sensor row is absent; two camera rows, two LiDAR rows, and three objects retaining their native counts without multiplication; explicit empty-vs-unknown label semantics; absent required calibration; nonfinite transforms; and mismatched calibration references. Assert payload bytes never appear in JSONL.
- [ ] Add analytic geometry tests: row-major sensor-to-vehicle transform maps a known sensor point correctly; vehicle-to-world composition uses the declared direction; native camera +x-forward/+z-up axes are retained; invalid rotation/homogeneous matrices fail within absolute tolerance `1e-6`. Preserve camera intrinsics/distortion and image-specific timing/pose rather than replacing them with frame pose. Test box dimensions as length/x, width/y, height/z, with heading in radians and scene-wide LiDAR object identities.
- [ ] Run focused `test_manifest.py` and `test_geometry.py` discovery; confirm failure.
- [ ] Implement a frame index from the union of observed keys, capped by sorted selected timestamps. Keep calibration, camera, LiDAR, scene-label and pose records distinct. Default components: `camera_calibration`, `lidar_calibration`, `vehicle_pose`, `camera_image`, `lidar`, `lidar_box`; labels may be unavailable under declared policy. A strict multimodal probe requires the selected camera, selected LiDAR, valid calibrations and frame pose; a single-shard diagnostic is always marked partial.
- [ ] Project metadata/key columns first; read image bytes only to measure selected image records, and range values only for selected LiDAR/frame records in bounded batches subject to decoded row-group ceilings. Emit range shape, return identity, finite-positive count and min/max range in metres; require flattened length to equal the shape product with four channels and use null extrema for zero valid returns. Retain no-label-zone counts/codes explicitly, flag unknown codes, and test absent returns and invalid shapes. Do not emit points, JPEGs, arrays, or thumbnails. Invalid sentinel values are excluded per the pinned source contract. Preserve no-label-zone provenance if interpreting zero object counts.
- [ ] Keep camera and LiDAR object-ID namespaces separate. Do not perform associations or motion compensation in this first slice. Preserve camera timing and rolling-shutter metadata, per-pixel LiDAR pose availability, native vehicle axes, transform direction and source field names. Never claim a synchronized point cloud from a range summary.
- [ ] Rerun focused suites; require pass. Add one test observing the requested Arrow columns to ensure metadata scans do not load large payload columns.
- [ ] Commit Task 3 files: `feat: emit deterministic Waymo scene manifests`.

## Task 4: Validate and atomically publish immutable runs

**Files:** Create `pipeline/run_store.py`, `pipeline/cli.py`, `tests/test_run_store.py`, `tests/test_cli.py`. Extend `pipeline/validator.py`.

**Interfaces:** `inspect_one(request: ProbeRequest, runs_root: Path, run_id: str) -> int`; `validate_run(run_dir: Path, source_root: Path | None) -> ValidationReport`. CLI exits: `0` validated, `2` invalid invocation/policy, `3` unavailable required input, `4` integrity/schema failure, `5` resource budget exceeded.

- [ ] Write failing tests for traversal run IDs, interruption before promotion, simultaneous same-ID runs, existing run refusal, source mutation during scanning, mutated output hashes, recipe drift, and a report mislabeled as complete despite partial modalities.
- [ ] Run focused CLI/store tests; confirm failure.
- [ ] Implement staging beneath the final runs filesystem, safe IDs matching `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`, exclusive per-ID locking, validation then same-filesystem rename, and no overwrite option. Keep failed diagnostics under a distinct failure directory; never publish them as validated runs. Rehash sources after reading and before promotion.
- [ ] Write `manifest.jsonl`, `sources.json`, `result.json`, and `report.json`. Result records implementation digest, schema/recipe/environment hashes, manifest hash, source inventory hash and parent lineage. Reports contain actual counts, duration, artifact bytes and precisely scoped process memory measurements. Source-revalidation absence is `not_checked`, never a claim that source hashes still match.
- [ ] Validate schema, record references, count consistency and artifact hashes before promotion. Reports exclude machine-specific input paths from deterministic manifests; paths used for local validation remain in private run metadata.
- [ ] Rerun focused tests; require pass, and verify complete runs remain unchanged after every failed operation.
- [ ] Commit Task 4 files: `feat: publish validated immutable Waymo runs`.

## Task 5: Add the dedicated offline runtime and dispatch gates

**Files:** Create `requirements.in`, `requirements.lock`, `build.sh`, `enter.sh`, `run.sh`, `insula/Dockerfile`, `insula/build_rootfs.sh`, `insula/enter_rootfs.sh`, `tests/test_runtime.py`. Extend recipe/verifier and CLI.

**Interfaces:** `run.sh emit-plan`, `run.sh build`, `run.sh verify-env`, `run.sh inspect-one --sample PATH --policy PATH --run-id ID`, `run.sh validate --run-id ID [--source-root PATH]`. Cache env is `WAYMO_CACHE_ROOT`; default `${XDG_CACHE_HOME:-$HOME/.cache}/sureal/waymo-perception`.

- [ ] Write failing dry-dispatch tests asserting only `build` is networked, source/repository/policy mounts are read-only, run cache is writable, offline entry uses a network namespace, and no CUDA device or credential directory is mounted. Paths with spaces and shell metacharacters remain individual arguments. Add a runtime/lock audit rejecting TensorFlow distributions and Waymo SDK dependencies, including transitive dependencies.
- [ ] Run `test_runtime.py` discovery; confirm failure.
- [ ] Resolve compatible PyArrow and JSON Schema validator versions on Python 3.10 into a hash-pinned transitive lock; record the actual successful versions and base image digest. Start by evaluating PyArrow 16.0.0 from the research baseline, without treating it as a raw-reader requirement. Verify lock installation in the dedicated image and prove TensorFlow is absent from its installed distributions and imports; do not install product dependencies into the host or Surflo environment. Add Torch/JAX only when an explicitly selected tensor operation requires them.
- [ ] Implement rootfs build/validation and offline default entry using the existing Insula pattern. Set explicit input/cache mounts and minimal environment. `emit-plan` works without rootfs or data; `verify-env` checks required imports, actual versions, rootfs marker, and a Parquet round trip inside isolation. Network namespace isolation must be tested by an actual blocked connection to a host test listener; a marker variable is insufficient proof.
- [ ] Run portable runtime tests, `bash -n` on all new shell scripts, build the image, and run `verify-env` when Docker/Podman and bwrap are available. Report infrastructure checks as blocked if prerequisites are unavailable; do not substitute host execution.
- [ ] Run all experiment tests and recipe verification. Update README with actual commands and measurements only; commit Task 5 files as `feat: isolate Waymo probe execution`.

## Task 5a: Validate the Waystone all-modality slice handoff

**Files:** Create `pipeline/slice.py`, `slice.schema.json`, `tests/test_slice.py`; extend CLI, recipe and README. Do not edit Waystone or duplicate its HDFS transfer/authentication stack in Sureal.

**Interfaces:** `validate_slice(slice_root: Path, receipt: Path) -> ValidationReport`. Add offline `run.sh verify-slice --sample PATH --receipt PATH`. The receipt is a proposed cross-repo handoff contract to adapt to what Waystone supplies, not an existing Waystone command or schema.

- [ ] Write failing tests for a two-context receipt containing geometry components plus segmentation, keypoints, associations and an unsupported component. Assert every expected available file is present and retains its recorded bytes/digest, regardless of whether the initial reader understands that component. Assert unsafe relative paths, duplicate destinations, checksum mismatch, over-budget slices and missing expected files fail verification.
- [ ] Test object-asset membership is explicit rather than inferred from context filenames. Assert upstream-unavailable modalities are reported separately from expected-but-not-ingested files. Test slice completeness independently from parsed-manifest completeness and full-HDFS-mirror completeness.
- [ ] Run `test_slice.py` discovery; confirm failure. Implement schema, lineage, cohort/coverage and byte/hash validation using local files only. Minimum handoff fields: receipt version, Waystone revision, resolved HDFS dataset root/inventory ID, local root, release/split/context cohort, complete component membership, per-object source URI/relative local path/size/content digest, measured total bytes, local size ceiling and availability evidence.
- [ ] Rerun focused tests; require pass. `verify-slice`, `inspect-one`, `inspect-pilot` and `validate` remain offline; data transfers run under Waystone’s own explicit acquisition/staging commands.
- [ ] Inspect the actual Waystone handoff before real-data execution and adapt the receipt mapping with a regression fixture. If Waystone has not yet produced the slice/budget, keep this integration gate pending while portable fixture work proceeds. Verify the delivered two-scene cohort and all available modalities without silently reducing it to the reader’s geometry allowlist.
- [ ] Commit Sureal validation and permitted compact evidence: `feat: validate Waystone Waymo slice handoff`.

### Observed Waystone capability and remaining dependency

Read-only inspection on 2026-09-29 found `docs/shared-hdfs-storage.md` and `python/waystone/storage.py` publish a shared namespace resolver via `waystone storage-prefix [--child CHILD --json]` and `hdfs_storage_path`. Use the resolver for namespace discovery rather than hardcoding the currently documented root. The current `AGENTS.md` places HDFS tooling and authentication in Waystone; its Python path uses PyArrow/libhdfs.

No Waymo-specific inventory, local two-scene slice command, generic slice receipt, or local byte-budget contract was found in that inspection. Prefix discovery does not prove dataset existence, permission, or completeness. The concrete dataset child path, local slice path, selection, size budget and handoff format therefore remain Waystone-owned decisions; consume its eventual outputs rather than manufacturing those decisions here.

## Task 6: Prove one authorized segment

**Files:** Modify `README.md`, `roadmap.md`; optionally track a redacted source-lock entry and compact report only when retention policy permits. Raw data and full manifests remain outside git.

**Interfaces:** Consumes Tasks 1–5a and the verified local slice; produces a validated real-data manifest, source inventory and reproducibility evidence.

- [ ] Select one context from the verified two-scene slice and record the processing profile, selected sensors/frame budget, byte ceilings and retention policy outside git. Keep the full all-modality slice intact; report stored component coverage separately from components interpreted by this initial reader. Verify its component inventory against the planned field mapping before running; fix any real-schema mismatch with a synthetic failing regression test first.
- [ ] Run `experiments/waymo-perception/run.sh emit-plan` and `experiments/waymo-perception/run.sh verify-env`; require declared offline conversion and verified environment.
- [ ] Run `experiments/waymo-perception/run.sh inspect-one --sample "$WAYMO_SAMPLE_ROOT" --policy "$WAYMO_POLICY_FILE" --run-id waymo-one-segment`; require schema/hash validation and explicit partial/complete status.
- [ ] Run the same input under run ID `waymo-one-segment-repeat`; compare manifest bytes/SHA-256. Require equality while allowing execution reports to differ.
- [ ] Run `experiments/waymo-perception/run.sh validate --run-id waymo-one-segment --source-root "$WAYMO_SAMPLE_ROOT"`; require source and output checks. Record frame/modality/object counts, actual input bytes, duration, memory scope, output bytes, availability and failure findings.
- [ ] Mark roadmap 05 complete only after this evidence exists. If sample/access is absent, mark the gate pending and stop before claiming runnable conversion. Commit permitted compact evidence as `docs: record Waymo one-segment probe`.

## Task 7: Measure a reduced pilot and decide the next consumer

**Files:** Extend `pipeline/cli.py`, `tests/test_pilot.py`; modify recipe, schemas, README and roadmap as required for the pilot interface.

**Interfaces:** Add `run.sh inspect-pilot --cohort PATH --policy PATH --run-id ID`. Cohort is a fixed list of contexts/component sources and selected frames, with explicit maximum segments, input bytes, output bytes and wall time. No wildcard expansion to an entire split.

- [ ] Obtain the explicit measured cohort/budgets before acquisition or launch. Write failing tests for exact-boundary budgets, one-over-boundary refusal, timeout, malformed context, partial cohort failure and stable ordering across contexts.
- [ ] Run `test_pilot.py` discovery; confirm failure. Implement bounded iteration and final all-or-nothing validation/promotion using the same manifest/store interfaces; retain failures separately.
- [ ] Run all experiment tests; require pass. Execute the fixed authorized cohort offline twice and compare manifest hashes, counts and completeness. Record wall time, memory measurement scope, input/output sizes and schema validity independently.
- [ ] Update roadmap 06 only with actual evidence. Produce a short decision under `research/first-consumer.md` for Sureal reconstruction, a maintained reference adapter, or TorchTitan export. A training bridge is a subsequent plan with its own task/model metrics, not part of this implementation.
- [ ] Commit Task 7 implementation and permitted evidence: `feat: measure bounded Waymo perception pilot`.

## Verification and scope review

Before each task commit, run its focused checks and `git diff --check`. Final portable gate:

```bash
PYTHONPATH=experiments/waymo-perception python -m unittest discover -s experiments/waymo-perception/tests -p 'test_*.py' -v
python experiments/waymo-perception/verify_recipe.py
git diff --check
```

Real-data gates remain distinct from synthetic success and runtime build success. Do not count a skipped sample, missing Docker daemon, unsupported schema, or unavailable bwrap as a passing execution gate. Review tracked outputs for payloads, credentials and machine-local paths; confirm no base dependencies or unrelated experiments changed.

Coverage: source facts and schema decisions → Tasks 1–3; storage/access → Waystone dependency; all-modality local handoff validation → Task 5a; runtime isolation and no-TensorFlow enforcement → Task 5; one-segment probe → Task 6; reduced pilot and consumer decision → Task 7. TensorFlow-free v1 reading, full upstream-to-HDFS ingestion, image undistortion, Torch/JAX point conversion, association joins and training each require a separate scoped follow-up if selected. Point-conversion verification must use pinned source equations, original analytic fixtures and permitted reference vectors; do not execute the TensorFlow upstream helper.
