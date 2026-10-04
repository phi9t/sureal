# Bounded scientific scene preprocessing implementation plan

**Goal:** Convert every selected Perception scene from generation-verified HDFS components into independently checked, sensor-indexed training records without accumulating a local raw dataset.

**Architecture:** Host Waystone performs authenticated transfers; an offline locked CPU Insula processes each source object. A scene-local derived working set supplies calibration, frame poses and per-pixel poses to reconstruction. Outputs retain original sensor identities and separate observations from supervision. Only independently validated scene outputs are published to an immutable HDFS namespace.

**Tech stack:** Existing Python 3.12/NumPy/Arrow CPU Insula, Waystone wrapper, stdlib host orchestration. No TensorFlow.

**Spec:** `.scratch/multimodal-perception/issues/07-scientific-protocol.md`, `experiments/waymo-perception/scientific-acquisition.candidate.json`, and the geometry/reconstruction contracts in tickets 03–04.

## Global constraints

- Retained engineering raw plus staged scientific raw: at most 2,147,483,648 bytes. One staged scientific raw object. Source object bytes count as raw even if renamed or placed under a derived directory.
- Proposed derived working-set cap: 16,106,127,360 bytes (15 GiB), including partial outputs and temporary serialization; freeze this under ticket 07 after a live scene pilot. Exceeding it fails the candidate without dropping scenes, returns or points.
- Acquisition session 90362 owns raw staging until terminal. Do not run a second raw staging orchestrator concurrently. Future transfer paths use an exclusive host lock shared by acquisition and preprocessing.
- All 103 scene memberships and all 17 native component inventories remain authoritative. Reconstruction uses required component subsets; unused families remain recorded rather than disappearing from provenance.
- Current-frame, all five LiDARs, both returns; TOP uses first-return per-pixel pose for both returns. Preserve explicit uncompensated status for non-TOP sensors. Stored camera projections are correspondences, not independently verified rolling-shutter projection.
- No source overwrite, silent missing-row fallback, train/held-out mixing or encoding of annotation metadata as physical features.
- No model training until ticket 07 closes. This plan implements data readiness, not scientific comparison completion. Preserve historical R0 code/receipts by adding focused modules.

## Review focus

1. A missing return differs from a present return with zero valid ranges; record presence explicitly and reject unsupported missing required evidence.
2. A populated LiDAR row without a TOP pose must fail; absence cannot become an identity transform.
3. Empty annotation tables are present-but-empty; absent components cannot become empty supervision.
4. Two rows with identical complete native identity must fail before any output is promoted.
5. A transfer or validation interruption leaves unpromoted outputs and resumes by verifying existing hashes, never trusting file existence.

## Task 1 — Admission and immutable source identity

**Files:** Create `experiments/waymo-perception/scientific-preprocess.py`; test `experiments/waymo-perception/tests/test_scientific_admission.py`.

Preparation implemented in `pipeline/scientific_admission.py` and `pipeline/source_integrity.py`, with live evidence in `research/scientific-admission-evidence.json` and `research/source-integrity-evidence.json`. The latter verifies bytes on the retained engineering slice, not a new scientific HDFS transfer. Host orchestration and actual staged-source transfer remain open; Task 1 is not complete.
Exclusive ownership is now implemented in `pipeline/staging_lease.py` and future acquisition launches use the shared cache-level `raw-staging.lock`. `research/staging-lease-evidence.json` proves live cross-process exclusion, exception release and real duplicate acquisition refusal. The existing acquisition remains pre-lease and is explicitly detected through live process argv; no marker file or stale lock is treated as proof of a live owner. Host preprocessing orchestration and actual staged-source transfer remain open.

`staged_source(record: dict, cache: Path, *, retained_bytes: int, limit_bytes: int, transfer_command: list[str] | None = None)` in `pipeline/staged_source.py` yields `(verified_path, evidence)` under that shared lease. Production uses Waystone; command injection is restricted to lifecycle fixtures. It refuses existing raw stage directories, admits retained plus declared bytes, enforces the remaining file-size allowance in the transfer child with RLIMIT_FSIZE, verifies size/SHA256/GCS-MD5 and removes its own temporary stage on every exit. `research/staged-source-evidence.json` records live controlled-transfer tests and refusal to overlap the actual live acquisition; production transfer through this context remains an open verifier.

`scientific-preprocess.py --scene SCENE --output DIRECTORY [--component TAG]` connects admission/staging to separate `pipeline.scientific_component decode` and `validate` Insula commands, with read-only decoded input for the checker. It writes `sidecars/COMPONENT` and `evidence/COMPONENT`, validates existing successful resume identities, and preserves/refuses unpromoted partial outputs. `research/scientific-component-evidence.json` proves the command boundary on native calibration/pose rows and real ownership refusal. Full scientific transfer, resume and scene processing remain unverified; this command currently prepares components, not scene reconstruction/publication.

**Interfaces:** `admit_scene(manifest: dict, records: dict, scene: str) -> dict` returns the exact official/research partitions, required component records, source SHA256 values and generations. `stage_source(record: dict, destination: Path) -> Path` downloads via the sibling Waystone wrapper and independently checks size and SHA256 before exposing the file to Insula.

- [ ] Write failing tests: changed generation/source hash, a missing required component, engineering-scene membership, duplicate component identity and conflicting research partition all reject. An empty annotation inventory admits as present.
- [ ] Observe failures, then implement admission against the candidate and completed acquisition records; never infer membership from filenames alone.
- [ ] Add raw capacity tests covering retained engineering plus active staged source; an object exceeding remaining capacity fails before transfer. Use exclusive locking and refuse concurrent acquisition ownership.
- [ ] Run tests live in CPU Insula for pure admission math; host transfer integration separately proves actual HDFS download-back hash checks. Record exact code/input identities and resource usage.

`scientific-preprocess.py --scene SCENE --output DIRECTORY --reconstruct` now connects all default sidecars to separate scene producer/checker Insula invocations under a single staged-LiDAR lifetime. `verified_sidecar_hashes` in `pipeline/scientific_preparation.py` admits hashes only after rechecking successful decode/check commands, matching native source/scene/candidate identities, complete checker/manifest evidence and every captured artifact hash. Successful scene resume also checks candidate/runtime/source-record/sidecar identities and all point/evidence artifacts. Partial scene outputs are preserved/refused. The combined derived budget includes component receipts/logs and scene evidence; publication remains a later phase. `research/scientific-preparation-evidence.json` proves live provenance rejection fixtures and actual reconstruction-mode refusal while acquisition owns staging. Full scientific transfer/reconstruction integration and successful resume are still unverified and must run after acquisition is terminal.

## Task 2 — Component sidecars with bounded native keys

**Files:** Create `pipeline/scientific_sidecars.py`; test `tests/test_scientific_sidecars.py` (both paths relative to `experiments/waymo-perception`).

**Interfaces:** `materialize_component(source: Path, component: str, scene: str, output: Path, remaining_bytes: int) -> dict` writes schema-versioned JSON field metadata plus non-pickled NPZ shaped arrays with original native keys, nullable fields, original array dtypes, native Arrow schema hash and source hash. It returns relative artifact names, hashes, sizes, native row counts and presence flags. This decoded representation permits direct bounded NumPy consumption without staging several raw Parquet objects together.

`iter_sidecar_rows(directory: Path, *, expected_manifest_sha256: str)` in `pipeline/scientific_sidecar_reader.py` reconstructs native-compatible rows with flattened NumPy `.values`, original `.shape` and null markers. The expected manifest hash comes from independently validated provenance; deriving it from the directory being admitted is insufficient. Verify manifest and per-record artifacts before yielding. All iteration must be exhausted to verify the final inventory.

- [ ] Fail-first fixtures pin exact keys and nullable/empty distinction for calibration, vehicle pose, TOP pixel pose, projections, segmentation and boxes. Reject duplicate identities and wrong contexts; reject allocation/output beyond the remaining budget.
- [ ] Implement streaming one native row at a time using existing `select_rows`/`array_field`; preserve schema and sensor identity rather than multiplying joined rows.
- [ ] Large sidecars are derived only when decoded into the declared key/payload schema; do not copy raw Parquet into this budget to evade the raw limit.
- [ ] Live verifier reopens every sidecar and compares key counts and payload arrays with the staged source before its raw file is removed. Persist checker evidence with original source hashes.

## Task 3 — Frame reconstruction and target gathering

**Files:** Create `pipeline/scientific_reconstruction.py`; test `tests/test_scientific_reconstruction.py`.

**Interfaces:** `reconstruct_scene(lidar_source: Path, sidecars: Path, output: Path, budget_bytes: int, *, verified_manifest_hashes: dict[str, str]) -> dict` uses the verified geometry implementation and emits one sensor/return record at a time, plus an immutable scene manifest. Manifest hashes come from the independent sidecar verification/publication chain and feed `iter_sidecar_rows`; input identities cannot be established by hashing arbitrary local files and trusting the result. Record identity is `(segment, timestamp, laser, return)`; point identity extends it with original `(row, column)`.

Implemented preparation is recorded in `research/scientific-reconstruction-evidence.json`: all 198 frames of one retained engineering scene matched the independently verified R0 reference (1,980 records; 36,214,548 points). Combined sidecars and reconstruction used 10,480,270,573 bytes. This validates the path on that scene; source staging/publication and full scientific-cohort acceptance remain separate gates.

- [ ] Write fail-first fixtures for TOP missing pose, changed frame pose, duplicate keys, non-TOP explicit motion policy, absent return versus valid empty return, both-return label gathering and mismatched projection shape.
- [ ] Implement bounded lookups without sensor/object Cartesian joins. Coordinate reference is the native vehicle frame pose, not an assumed timestamp-aligned transform.
- [ ] Observation payload: XYZ, physical intensity/elongation and source pixel identity. Evaluation/supervision payloads: NLZ, native camera projection, semantic/instance labels and boxes, all in separate named arrays/namespaces.
- [ ] Preserve full valid measured points before downstream ROI clipping/sampling. No training-only feature choice may erase source support needed for evaluation.
- [ ] Enforce cumulative derived bytes before publication; partial outputs remain explicitly unpromoted after failure.

The offline scene boundary is now `python -m pipeline.scientific_scene_command reconstruct SOURCE SIDECARS TRUSTED_MANIFEST_HASHES_JSON RECORDS BUDGET_BYTES`, followed by a separate `validate SOURCE SIDECARS TRUSTED_MANIFEST_HASHES_JSON RECORDS CHECK_JSON` invocation. The provenance JSON must be supplied from independently verified component receipts, not invented from arbitrary local sidecars. `research/scientific-scene-command-evidence.json` records live native-schema command fixtures, receipt overwrite refusal and changed-source rejection without checker output. Host orchestration and actual scientific-scene execution remain open.

## Task 4 — Independent scene validation

**Files:** Create `pipeline/scientific_scene_validate.py`; test `tests/test_scientific_scene_validate.py`.

**Interfaces:** `validate_scene(scene_manifest: Path, sidecars: Path, records: Path) -> dict` derives checks from reopened arrays and native sidecars; it does not trust producer pass flags.

- [ ] Fail-first mutations alter one source pixel identity, return number, semantic value, physical feature, coordinate, input hash or artifact hash. Each must be rejected.
- [ ] Check complete frame/sensor/return inventory and missing/present flags, original point/projection/target order, physical-feature versus annotation separation and valid-range conservation.
- [ ] Reuse independent scalar-ray equations from `reconstruction_validate.check_coordinates`; geometric tolerance is 1e-6 metres. Compare all target/pixel values exactly, not just sample counts. Check representative rays in every nonempty record.
- [ ] Independently compare sidecar acquisition identities and native frame/sensor cardinalities with completed source records. Aggregate counts alone are insufficient to prove sensor enum membership.
- [ ] Capture a separate live checker command, runtime identity, output hashes, elapsed time and peak RSS. Any missing assertion leaves the scene unpromoted.

Preparation implemented in `pipeline/scientific_scene_validate.py`, with live evidence in `research/scientific-scene-validation-evidence.json`. Replay command: `python3 experiments/waymo-perception/verify-scientific-scene.py OUTPUT_DIRECTORY`. The full retained engineering scene passed exact source-pixel/features/target reconciliation and independent scalar geometry samples in every nonempty record. Physical features follow the existing lossless float64 promotion; NLZ, projections and segmentation retain native dtypes. Rehashed payload/provenance/inventory corruption fixtures reject. Scientific source staging, full-scene orchestration/publication and complete cohort validation remain open; this preparation does not complete Task 4 for scientific scenes.

## Task 5 — HDFS publication and replay loader

**Files:** Extend `scientific-preprocess.py`; create `pipeline/scientific_dataset.py`; test `tests/test_scientific_dataset.py`. Packaging and independent archive verification live in `pipeline/scene_archive.py` and `pipeline/scene_archive_validate.py`, with their corresponding tests.

`create_scene_archive(points: Path, archive: Path, *, expected_report_sha256: str, sidecar_bytes: int, budget_bytes: int) -> dict` checks the independently supplied reconstruction manifest and every member hash, then writes an uncompressed deterministic USTAR archive: manifest first, sorted point filenames, regular members only, uid/gid/mtime zero and mode 0644. Admit packaging capacity before creating the archive, including sidecars, original point records, archive headers/padding and payload. `validate_archive(archive: Path, *, expected_report_sha256: str, expected_archive_sha256: str) -> dict` independently streams every canonical member against the trusted manifest without extracting paths.

**Interfaces:** `publish_scene(validated_manifest: Path, hdfs_root: str) -> dict` uses an immutable namespace keyed by contract/content identity and scene; publishes the manifest last. `iter_scene_records(archive: Path, publication: Path, *, expected_publication_sha256: str, usage: str, max_record_bytes: int = 134217728)` in `pipeline/scientific_dataset.py` verifies the supplied publication identity and the complete archive before yielding bounded records. Engineering-only publications accept only engineering use; scientific publications require matching official/research partition membership.

Each returned record separates `observations` (XYZ and physical range/intensity/elongation), `identity` (native frame/sensor/return plus original pixels), `targets` (native segmentation when present), `evaluation` (NLZ) and `correspondence` (stored camera projection). Absent returns remain explicit records with empty payloads. Replay creates no unpacked scene cache. Projection coordinates are checked for finite integral values while preserving their native float32 storage; requiring an integer storage dtype would incorrectly reject real v2 inputs. Detector boxes and camera image inputs still need their own verified native-key assembly; this point-record loader does not establish those task inputs.

Native segmentation instance ID -1 is preserved independently of semantic class validity; valid stuff labels must not be masked away because no instance is assigned. `verify-archive-dataset.py OUTPUT_DIRECTORY` captures current live fixture and two-pass engineering archive replay receipts. See `research/scientific-dataset-evidence.json`; the successful engineering replays do not freeze scientific splits or establish scientific task inputs.

- [ ] Fail-first tests cover interrupted publication, conflicting existing content, corrupt download, duplicate scene identity, split leakage and evaluation metadata accidentally requested as physical input.
- [ ] Use Waystone put without overwrite; accept existing files only after independent download-back hash agreement. A manifest is publishable only after every referenced output has verified mirror evidence.
- [ ] Package decoded records for transfer rather than issuing one HDFS subprocess per point file. Delete the upload archive before downloading its verification copy; retain the independently validated source records until publication succeeds. A verified archive's hash is part of its immutable HDFS filename. Engineering archives retain an explicit engineering-only role and cannot become scientific train/validation examples.
- [ ] Keep the local derived working set bounded and evict only independently published artifacts. Loader cache verifies hashes on every admission and never uses a producer status flag as verification.
- [ ] Live two-pass replay requires identical original identities, coordinates, physical features, labels and source provenance. The two passes use separate output/cache directories.

Publication metadata preparation is implemented in `pipeline/scientific_publication.py`. `publication_manifest` requires admitted membership and all 17 generation/source/mirror identities, successful independent scene commands, a matching independently checked reconstruction report, archive member/byte identities and download-back SHA agreement. It preserves scientific official/research partitions and a hash-keyed HDFS URI. The caller must independently verify supplied scene/archive receipts against trusted identities before calling it; this pure metadata contract performs no transfer and cannot prove HDFS availability. `research/scientific-publication-contract-evidence.json` records live fixtures rejecting failed checks, mismatched source/report/partition/archive/mirror identities and a missing source family. Actual scientific packaging, publication-last sequencing and replay remain open.

Fresh `scientific-dataset-live-d` evidence verifies seven fixture groups, including all legal scientific partition combinations, cross-partition usage rejection and malformed/duplicate partition rejection, followed by two full engineering archive replays with exact native-array agreement. This replaces the current loader evidence after tightening duplicate membership rejection. Scientific-cohort archive execution and source-pinned acceptance remain required separately.

## Task 6 — Full cohort readiness evidence

**Files:** Create `research/scientific-preprocessing-verified.json` only after verification; update ticket 07 and the execution ledger.

- [ ] First run a complete training-scene pilot and an eligible camera-validation scene through separate producer/checker invocations; measure total raw/derived capacity, elapsed time, peak RSS and bytes. Freeze the derived cap only after it is feasible without changing support.
- [ ] Process every selected scene and reconcile manifests against all 1,751 acquisition records. Report annotation eligibility and native semantic support after valid-range gathering; include rare-class limitations.
- [ ] Audit every source generation, output hash, split membership and independent live receipt. Re-run corrupted-artifact and interrupted-publication rejection fixtures against the current code.
- [ ] Publish exact replay commands and resource totals. This closes preprocessing evidence only; statistical protocols, model budgets and ontology decisions must also pass before ticket 07 closes.

## Self-review

The plan retains the full cohort, distinguishes annotations from observations, covers every review-focus failure in an owning task, preserves native motion/return conventions and requires both source-derived correctness and HDFS replay evidence. It introduces no new model result, paper-reproduction claim or automatic ticket closure. Numerical optimization and cross-modal class maps belong to the scientific preregistration, not this loader.

## Scientific pilot evidence

The first training scene passed all seven production staged-source sidecar producer/checker pairs and native scene reconstruction/check, then actual immutable HDFS publication and two scientific loader replay passes. See `research/scientific-training-pilot-evidence.json`, `research/scientific-training-publication-evidence.json` and `research/scientific-training-replay-evidence.json`. Successful resume preserved all eight original receipt identities. The measured publication working set was 13,060,255,069 bytes. This point-record pilot does not establish camera/detector task assembly, a second camera-validation pilot, full cohort processing or protocol acceptance. Complete bounded retention/publication/eviction before accumulating further complete scientific scenes.

## Decoded sidecar retention

`pipeline.component_archive.create_component_archive` packages externally verified decoded component files in deterministic USTAR form with a bounded `bundle.json` inventory/provenance manifest. `pipeline.component_archive_validate.validate_component_archive` independently streams every member without extracting paths. Live preparation evidence is in `research/component-archive-evidence.json`. Publish remaining sidecars and independently verify the HDFS mirror before eviction; point payloads already have separate scientific archive/replay/recovery evidence. The first pilot’s point eviction is recorded in `research/scientific-point-eviction-evidence.json`. Historical artifact receipts remain provenance after explicit eviction and cannot be mistaken for currently resident payloads.

## Camera task input preparation

Add separate `pipeline/camera_sidecars.py` and independent `pipeline/camera_sidecar_validate.py`, with `tests/test_camera_sidecars.py`. Support native camera_image, camera_segmentation and camera_box tables. Preserve original Arrow schema/source hashes, complete native keys and every scalar/list/nullable field. Binary JPEG/PNG fields are stored exactly, with manifest-backed SHA values; do not decode/re-encode or invent label coverage from absent box rows. Bounded one-row processing and admission before writing a row keep local memory/storage explicit. Independent validator reopens source Parquet, compares native keys/scalars/nulls and original binary bytes, checks complete artifact inventory and output byte accounting. Live fixtures precede actual staged-source integration; adding these inputs must retain the shared raw lease and combined working-set cap. This does not permit training before ticket07 closes.

### Camera immutable bundle integration

Create `publish-scientific-camera.py`. Admission requires an externally audited camera-evidence SHA and all three component receipt hashes/current code/source identities/decoded artifact hashes. Package exactly those receipt-backed camera sidecars using the tested deterministic component_archive producer and independent streaming validator; include official/research membership and camera source receipt/generation/hash provenance. Count all resident scientific-working-root bytes before archive serialization. Waystone put to camera-bundles-v1/scientific immutable SHA URI, remove original archive before download-back, independent full bundle check, then publish metadata last and verify its roundtrip. Record live/runtime/candidate/source/output/timing/resource evidence. Preserve local original bytes until independent publication/replay acceptance and explicit verified recovery-based eviction. No heuristic box/panoptic identity join or unlabeled-empty inference.

### Bounded camera archive replay

Create `pipeline/camera_dataset.py` and `tests/test_camera_dataset.py`. Iterator requires independently trusted publication SHA, official/research usage admission, and full independent component-bundle validation before first yield. It uses a seekable immutable tar without extracting files, verifies component/row manifests and original binaries, and limits resident row bytes. Camera image rows expose observations only; native segmentation and boxes expose targets only, with namespaces distinct. Preserve complete original keys; never infer image annotation coverage from absent box rows. Live analytic fixtures test exact bytes, split/engineering refusal and label separation; then two actual scientific loader passes independently compare original decoded sidecars and decode real JPEG/PNG geometry/support. Model training remains gated on ticket07.

## Sequential full-cohort execution driver

Create `process-scientific-cohort.py` to orchestrate existing verified commands, with a separate nonblocking queue lock and exact selected-scene membership. Each scene passes eight source/reconstruction receipt/artifact audits, point publish/audit/two replay/audit/recovery-first eviction, seven-family sidecar publish/audit/eviction, camera HDFS processing/audit/publish/audit/two replay/audit/eviction. Immutable per-scene checkpoint retains every promoted receipt and recovery identity and current driver/code/runtime/source/cohort hashes. Successful existing checkpoints are rehashed before skip; partial directories stop and remain reviewable. The first invocation adopts the currently processing scene only after that process is terminal, using an explicit initial processing directory. Never alter selected cohorts, silently skip failed scenes, train models or close ticket07. Actual first complete queued scene provides live orchestration verification before unattended remaining-scene execution.
