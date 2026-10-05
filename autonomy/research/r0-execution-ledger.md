# R0 execution ledger — 2026-09-29

User authorized continuing main research/resource goals. Implement R0 inline
using the approved mathematical contract and existing two-scene slice.

## Runtime observations

The current managed environment denies Docker daemon access:
`connect /var/run/docker.sock: operation not permitted`.
A fresh `bwrap --unshare-net --ro-bind / / -- /bin/true` fails:
`Failed to create NETLINK_ROUTE socket: Operation not permitted`.
The existing tracer runtime test also fails for that same reason. The earlier
successful runtime runs occurred before the permission profile changed.
Do not skip this test, silently use host processing as Insula, or mark R0 done.
No elevated-permission tool route is available in this session.

Ruling: continue the pure CPU reference math while dedicated runtime is blocked.
This makes useful progress without substituting unverified native geometry or
false isolation claims. Full real-data reconstruction remains pending.

## Mathematical implementation

Added `pipeline/geometry_foundation.py`: float64 SO3/SE3 exp/log, rigid
inverse/apply, rotation-first right-perturbation point Jacobian and adjoint,
polar conversion/Jacobian, half-open BEV indices, optical pinhole projection,
relative radial velocity, covariance transport and timestamped sensor chain.
No TensorFlow, SymForce installation, dependency additions or generated
third-party code. This core is not yet a native Waymo range/camera adapter.

Test-first evidence: initial eight fixtures failed on missing module, then
passed. Covariance/sensor-chain fixture failed on missing interfaces, then
passed. Includes independent coupled-SE3 translation, noncommuting transforms,
near-pi rotation reconstruction, manifold finite differences at two step sizes,
100,000-sample linear covariance check, singular polar input, invalid optical
depth, upper-edge grid exclusion and radial-vs-full velocity distinction.

Current verification after review: 11 foundation tests pass; full suite 27 tests, 26 pass,
1 runtime failure from the managed environment. Dedicated rootfs, full-scene
range geometry, calibrated projection views and reproducibility gates remain
open. Do not infer completion from passing mathematical primitives.

## Review corrections

Independent review reproduced upper-edge BEV rounding producing an invalid
cell and a tiny negative covariance amplified into negative variance. Added
failing regression fixtures, then bounded valid BEV indices and made PSD
validation strict. The geometry suite now has 11 tests. No runtime limitation
was hidden by these changes.

## 2026-09-30 live M1/M2 progress

M2: verify-geometry.py executed all 11 analytic/manifold/boundary/covariance fixtures inside verified CPU rootfs-v2. Independent host reconciliation rehashed code and test log, checked test completeness, runtime lock and prerequisite M0 receipt identity. research/m2-verified.json records closure; ticket 03 verified-complete. Radar fixtures are synthetic; this does not reconstruct any native sensors.

M1 first full live native replay: 143625 rows, manifest SHA256 70190074c7d443632523a5c3273d5ead74f4fcddea653addee3a2fa2efa01bcf; 105.9705 seconds producer runtime and 1013366784 peak RSS bytes. Separate live validator returned passed/source_revalidated true. All 10 adversarial tracer tests passed live.

M1 formal receipt run: verify-native.py launched with output ~/.cache/waystone/waymo-perception/insula/m1-live-b. Active exec session 60281; poll before any restart. Wrapper retains producer, independent validation and adversarial test logs plus exact commands and UTC timings. M1 remains implementing until this run completes and its receipt is independently audited.

Downloaded pinned upstream range_image_utils.py and v2 lidar_utils.py into the external upstream cache for M3 inspection; no TensorFlow source imports executed.

M1 closed: formal run m1-live-b completed producer, separate native source validator and ten adversarial tests live. Independent post-run audit recomputed every retained artifact and candidate hash, checked runtime content/lock, validator output, test count and baseline manifest SHA. research/m1-verified.json records the receipt identity; ticket 02 verified-complete.

M3 kernel progress: geometry.py implements pinned Waymo reversed inclination order, centered descending-column azimuth with extrinsic yaw correction, positive finite range ordering and TOP world-pixel/frame-reference compensation. Four tests were observed failing before implementation and now pass live in Insula. Native adapters, real sensors, projections/semantics and M3 receipt remain pending. No reconstruction completion claimed.

## M3 native adapter pilot — 2026-09-30

Added sensor_records.py: native streaming Arrow records, nullable array/shape validation, pixel bounds and exact projection/segmentation gathering from retained original pixel coordinates. Two adapter tests were observed failing before implementation and now pass inside verified Insula, including intentionally reordered pixel identities.

Added reconstruction_probe.py to process one labeled and one unlabeled frame from each acquired scene, all five LiDARs and both returns. TOP uses first-return pixel poses for both returns; other sensors are explicitly uncompensated. Saves physical features separately from NLZ metadata, original pixel identities and available targets. Independent scalar ray calculations include extrinsic yaw correction and elementary RzRyRx pixel poses, checked at distributed original pixels with 1e-6 meter tolerance. Reopens each NPZ and checks target/key preservation.

Live pilot launched via enter.sh: output insula/m1-output/reconstruction-pilot-a. Exec session 76507; first scene completed two frames. Poll this handle before relaunching. M3 stays implementing until pilot completion, broader real-data checks and candidate-specific independent receipt validation; this pilot does not close full-cohort reproducibility or research metrics.

Pilot finished: 40 sensor/return records, 715060 points. Both scenes completed and every sampled scalar-coordinate check met 1e-6 m tolerance. Independent post-run artifact rehash passed. m3-pilot.json records bounded coverage and resources; M3 remains open.

## Full acquired-cohort reconstruction

Replaced pilot payload dictionaries with OrderedLookup bounded native-key cursors and Arrow NumPy payload extraction. Test observed missing cursor before implementation; three native adapter tests now pass live. Producer now supports --full, enforces 16 GiB output budget and derives required sensor/return records from selected frame/calibration counts.

Live reconstruction-full-a completed all 397 frames, 3970 sensor/return records and 71891534 positive finite range points. Distributed independent scalar-ray coordinate checks passed at 1e-6 m for all emitted records. Output covers every acquired LiDAR and both returns with original pixels, physical features, NLZ metadata, supplied camera projections and available native semantics.

Independent reconstruction_validate.py now reopens sources and emitted NPZs without calling the reconstruction/gather functions. It verifies source hashes, native-key completeness, pixels/features/NLZ/projection/semantic arrays and coverage, including missing labels and explicit motion policy. Validation launched in Insula; poll the active session from the current tool result before relaunching. M3 remains open until this validation, additional adversarial checks and complete receipt audit finish.

Full producer resource observation: 72.7986 s, 684540 KiB peak RSS, 6696917932 output bytes (under 16 GiB cap). Independent validator active exec session: 20235. Producer-only completion does not close M3.

## Independent reconstruction validator strengthened

The first full source validator completed successfully: 3970 records, 397 frames, 71891534 points, native source hashes and exact pixels/features/NLZ/projections/segmentation reconciled. It initially checked XYZ shape/finiteness but did not independently recompute coordinates. Added check_coordinates using separate scalar/homogeneous equations and linear solve for frame-reference conversion; two live tests verify known rays and reject incorrect XYZ, extrinsics and missing pose compensation.

Formal M3 run: verify-reconstruction.py starts producer, strengthened independent validator and ray/identity/validator fixtures in the same locked CPU Insula. It freezes candidate hashes before execution, retains exact commands/logs/UTC/resource observations and full artifact hashes, and checks prior M0/M1/M2 evidence identities. Current output insula/m3-live-b, active exec session 33391. Poll before considering any restart. M3 stays open until complete run and receipt audit.

Timing/projection boundary: TOP compensation uses supplied pixel poses and vehicle label-reference pose. Non-TOP records are explicitly uncompensated; they do not gain per-pixel motion compensation by sharing a frame key. Camera correspondences are dataset-supplied, preserved as evidence; this implementation has not reproduced rolling-shutter-aware moving-point projection. Optical camera timing, occlusion and object-motion limitations must accompany M4 views and later fusion. Missing segmentation is explicit; NLZ is output metadata, separate from physical encoder features.

Read-only hardware inventory: eight NVIDIA B200 devices with 183359 MiB each observed; some devices currently hold other workloads. This is capability evidence, not reservation, GPU runtime verification or permission to interfere with jobs. Scientific resource caps remain to be selected after R0.

## M3 closure and M4 preparation

Formal M3 candidate m3-live-b completed full producer, independent native-source and scalar-coordinate validator, four ray fixtures, three sensor-identity fixtures and two coordinate-validator regression fixtures. Independent receipt audit recomputed all retained artifact/candidate hashes and runtime content; source-revalidated result covers 3970 records, 397 frames and 71891534 points with sampled coordinate error below 1e-6 m. research/m3-verified.json records closure; ticket 04 verified-complete. Timing/projection limitations documented above remain binding.

M4 preparation: inspection.py defines explicit display mappings for range images (unobserved NaN), BEV density (x horizontal, y upward, half-open bounded cells), and both supplied camera projection slots with retained point/slot IDs. Three tests initially failed before implementation; live tests now pass. Corrected resolution shape mismatch against the existing geometry core during testing. No view-generation milestone has yet completed.

## M4 live inspection generation

Added inspection_views.py and inspect-scene.py. Verified geometry mounted readonly at /opt/reconstruction while native source stays readonly /source and fresh output is bounded /outputs. Current run m4-live-a produced 131 artifacts across four frames: one TOP-segmentation-labeled and one unlabeled frame from each scene, all five cameras, all five LiDARs and both returns. Includes range images, aggregate BEV density and explicit oblique point-cloud views, supplied-projection camera overlays with original point/slot/pixel IDs, available native semantic arrays and coverage/provenance report.

Separate inspection_validate.py independently derives BEV density using histogram2d and checks original camera bytes, source-geometry hashes, retained sample/pixel IDs, both projection slots, image bounds and rendered overlay coordinates. Active validator exec session 1500. M4 stays implementing pending validation, visual review, extra semantic/range reconciliation and its receipt audit.

M4 validator first run exposed integer-valued projection coordinates stored as floating arrays; direct NumPy image indexing rejected them. Validator now explicitly verifies finite/integral native coordinates before converting to integer indices. This is a checker type-handling correction; M4 remains open and validation must rerun.

## M4 validator correction and expanded checks

Corrected floating-but-integral projection pixel indexing: require finite integral native coordinates, then cast for array indexing. Separate live validator passed m4-live-a: four frames, 20 cameras, 40 sensor/return views, 131 artifacts. Visually inspected first scene front camera overlay; supplied TOP points follow observed surfaces and retain original image geometry. Visual inspection is supplementary evidence only.

Expanded validator additionally reconciles range grayscale values and unknown support against retained physical range/pixel arrays, TOP semantic IDs and unobserved masks against native point targets, and camera semantic arrays against independently decoded source panoptic images.

Formal M4 candidate now runs producer, expanded independent validator and all three display fixtures, freezes candidate hashes and retains commands/logs/UTC/source/geometry/runtime/output identities. Output insula/m4-live-b; active exec session 92818. M4 remains open pending that run and independent receipt audit. Do not launch M5 execution before its prerequisite closes.

## M5 reproducibility execution — 2026-09-30

M0–M4 verified-complete. Started second formal full-cohort reconstruction using unchanged verify-reconstruction.py, geometry, adapters and independent validator; output insula/m3-live-c, exec session 62689. Started second formal full native replay using unchanged verify-native.py; output insula/m1-live-c, active session recorded in current tool result. Poll handles before any restart. Every repeated stage independently validates its own source lineage and adversarial fixtures.

Next: compare runtime/code/source receipt identities and geometry artifact hashes/coverage for m3-live-b versus c, and native manifest/source keys for m1-live-b versus c. Repeat geometry fixtures/views where needed, record live comparison receipt and publish R0 limitations/resource report. Resource fields and UTC logs may differ; deterministic source-key and geometry content must reconcile. No scientific model or held-out training result follows from R0 closure alone.

Native repeat active session 67733; geometry repeat 62689. Added r0_compare.py for later live independent rehash of all retained stage artifacts, exact candidate/runtime/cohort comparison, all 3970 geometry NPZ hashes/record identities, native manifests and source inventories. It records only engineering reproducibility, never learned-model quality. Not executed until repeat stage receipts complete.

Geometry repeat m3-live-c completed producer, independent full source/scalar validator and all nine ray/identity/validation fixtures. Exec session 62689 terminal success. Native repeat 67733 still live at last poll; keep polling same handle. Comparison remains pending that receipt.

Native repeat m1-live-c also completed producer, independent source validator and ten adversarial fixtures; session 67733 terminal success. Live reproducibility comparison launched with readonly mounts of both geometry and native run outputs, comparison output insula/m5-live-compare. Active comparison session 51293; poll before restart. It independently rehashes retained artifacts and matches code/runtime/cohort/native/geometry identities. M5 remains open pending comparison result and receipt/coverage closure audit.

M5/R0 closed: live comparison 51293 returned exact equality of 3970 geometry artifacts/native manifests under equal code/runtime/cohort; repeated M2 and M4 candidates passed and their code/runtime/artifacts independently reconciled. research/m5-verified.json and r0-geometric-insula.md record closure. Scientific work remains unexecuted.

Scientific readiness: authenticated GCS listed official training/lidar_segmentation shard names into external training-segmentation-inventory.txt. An attempted ls --format=json failed (unsupported format); corrected to native URI listing, command completed. Listing establishes object names only, not populated label rows or selected cohort. Ticket 07 preparing, not complete.

## Scientific cohort preparation

Official GCS inventories expose 798 training and 202 validation LiDAR-segmentation and camera-segmentation shard names each. Object presence is not populated supervision. Deterministic whole-segment selection implemented with duplicate/official-partition overlap/insufficient-support rejection. Two tests observed failing before implementation, then passing live in Insula.

scientific-cohort.candidate.json selects 64 train, 8 development (from official training), and 16 held-out official validation segments, excludes both engineering scenes, and records inventory hashes plus seed list 17/29/43. Candidate only: generations, label rows/class coverage, full modality inputs, resource caps and evaluator readiness not frozen or verified. No training/held-out comparison has begun. Acquiring first selected training label object's authoritative metadata to establish generation/size provenance before label coverage audit.

## Scientific supervision acquisition/audit

Added audit-cohort-labels.py: resolves generation-pinned object metadata, checks byte size and GCS MD5/SHA256, stages one bounded label object, mirrors into canonical Waystone HDFS raw official split/component/scene path, downloads back and verifies SHA256, then runs label_coverage.py offline in dedicated Insula. Temporary payloads are removed after each record; small source/coverage records remain in external cohort-label-audit cache.

First attempt stopped on missing HDFS parent; enabled documented --mkdir-parents. Input/output staging directories are siblings so entry rejects no overlap. First six label objects (LiDAR and camera segmentation for three training segments) successfully mirrored, roundtripped and inspected live; native rows: 19/100, 30/100, 50/100. Their semantic counts retain category zero/unknown and use the semantic channel rather than instance IDs. A live fixture caught acceptance of negative categories; added rejection and the fixture now passes.

Remaining candidate supervision audit launched resumably. Current active exec handle recorded by the tool call; poll before restart. Existing completed object records are skipped. All 176 potential selected label shards must be accounted for before task 07 coverage is accepted; six initial records do not freeze the cohort or prove model quality.

Remaining supervision audit active exec session 85848. No completion or readiness claim until this process is terminal and selected source/coverage records are independently reconciled.

## TF-free native evaluator build preparation

Fetched pinned upstream commit 99a4cb3ff07e2fe06c2ce73da001f850f628e45a into external metrics-source cache, checking out native proto/math/common/metric sources. Source audit of selected native dependency graph found protobuf, Abseil, glog, OpenSSL and zlib dependencies; no TensorFlow headers/import execution. Added evaluation/CMakeLists.txt and Dockerfile to compile unmodified native detection/segmentation implementations, command-line tools and their upstream regression tests without the Python TensorFlow wrappers.

Dedicated evaluator image build active session 28814; source-pinned image candidate only. Build/runtime package closure, native regression tests, pinned fake-data metric expectations, no-TensorFlow verification and dedicated live evaluator receipt remain pending. Ticket 09 is not complete from source inspection or image build initiation. Supervision audit continues in session 85848.

Evaluator build 28814 failed on BoringSSL-specific BN functions in exactfloat.cc. Diagnosis: CMake unnecessarily included exactfloat, absent from the pinned upstream native metric dependency graph (polygon2d/box2d/segment2d do not depend on it). Removed that extraneous target and OpenSSL link from the recipe; unmodified metric sources retained. Build retry active handle from tool result; complete log external metrics-build.log. No evaluator pass claimed.

Supervision audit found a genuine empty camera-segmentation table for training segment 3894883757914505116_1840_000_1860_000 (LiDAR table populated). Explicit empty state retained; candidate selection/coverage must account for it and must not call object presence complete multimodal supervision.

Native evaluator retry active exec session 64455; supervision audit active 85848. Poll existing handles before any relaunch.

## Native metric core live verification

Evaluator image built successfully after removing unrelated exactfloat target. Dedicated metrics-rootfs materialized and content-locked from image sha256:c0018cf57e482c6a9e6623ea32f29c6039f22f5dafb0f3311bad6d411a7bb135. verify-native-metrics.py ran six upstream detection regression tests and one segmentation regression test (with multiple scenarios), both pinned fake-data CLI examples, and dependency check inside offline rootfs; all passed. TensorFlow cannot be imported; detection ldd closure contains none.

Independent retained-artifact rehash and expected-score comparison passed all published detection breakdowns and native segmentation fake-data values (miou .00395302; car/pedestrian .0434832). research/native-metric-core-verified.json records bounded verified scope. Ticket 09 remains open for export/configuration, full dynamic closure, camera semantics and failure behavior.

Important parser finding: pinned detection CLI may print a parse error and return normally. Adapter must validate native input/output contracts and reject parse failures or missing expected metric output, not only exit zero. No trained model evaluated yet.

Native evaluator live session 29589 is terminal success; its bounded parity audit completed. Supervision acquisition/audit remains active in session 85848; continue polling that handle. Source object records are accumulating under cohort-label-audit and are not a frozen scientific protocol yet.

### Default native detection adapter boundary

Added fail-closed parsing for the pinned default 3D metric CLI. Four tests were observed failing before implementation, then passed inside the locked live metrics Insula. A real malformed prediction protobuf produced upstream `Failed to parse predictions.` with exit code zero; the adapter rejected it. Valid fake predictions matched all 32 pinned published AP/APH breakdown expectations within 1e-6. Independently reopened all candidate/output hashes and recorded `research/detection-adapter-verified.json`. This does not close ticket 09: export schemas/configuration, remaining metric families and dependency closure still require evidence. Cohort audit session 85848 remains live, now processing development shards after the selected training cohort.

### GPU runtime preparation

GPU inventory confirmed B200 device 1 unused at preparation time. Created a dedicated Python 3.12 Torch 2.9.1+cu130 / Torchvision 0.24.1+cu130 dependency closure with generated wheel hashes, Arrow/NumPy/Pillow pins, and no TensorFlow. Build driver verifies the exact local CUDA base image ID before building; it does not treat a mutable tag as provenance. First Dockerfile attempt using the full image hex as a FROM name failed parsing and was corrected to an identity-checked local tag. Image build is active under exec session 84601; no GPU gate has passed yet. Added an analytic GPU forward/backward and representative convolution verifier for subsequent locked live entry. Cohort audit session 85848 remains active.

### Completed cohort audit and live GPU entry in progress

Session 85848 terminated successfully after all 176 selected label shards. Independently reconciled scene/component identity, generation-pinned URLs, HDFS roundtrip hashes, semantic element counts and empty/populated status in `research/scientific-label-coverage.json`. Camera annotation availability is 58/64 train, 6/8 development and 1/16 validation, so the primary camera/mask evaluation cohort remains an open protocol requirement. GPU image build completed with ID sha256:46bdaa6e8d9058d7e09419085dfcf9a4527e801330045ae8e0f387f454413b86. Session 19832 is materializing and hashing the 13GiB dedicated rootfs before live computation; do not restart while it remains live.

### Actual GPU computation passes

GPU attempt b failed CUDA availability. Diagnostic cuInit returned 100 with CUDA_VISIBLE_DEVICES=1, then cuInit=0 and a real tensor allocation succeeded when ordinal 0 selected the sole mounted host /dev/nvidia1. The namespace enumerates its only exposed GPU as ordinal 0. Corrected only this environment selection, retaining single-device mounts. Live run c passed analytic float64 matrix values/input and weight gradients plus representative convolution forward/backward. Reopened candidate/output hashes and recorded `research/gpu-computation-probe.json`; ticket 08 remains open for isolation, failure injections and independent numerical artifact checks. Also acquired an official-validation camera-segmentation size inventory for coverage-only cohort discovery; file size is a screening hint, not proof of annotations.

### Coverage-based camera cohort audit and stronger GPU artifacts

Recorded `camera-coverage-audit.candidate.json` before model outcomes: screen official validation shards above the observed 10204-byte empty table size, exclude both engineering scenes, audit all 18 candidates, and select the first 16 native-coverage-eligible scenes in a declared SHA256 order. Size is only a screening hint. Audit session 77207 is live, mirroring both segmentation families through HDFS and running native coverage in Insula. Initial candidates have 495 populated camera rows. GPU probe now exports actual matrix inputs, outputs and gradients; independent NumPy validator derives results with einsum and gradient equations. Candidate rerun session 61260 remains live against the same locked rootfs; previous candidate c does not prove changed candidate d.

### Ticket 08 closes with independently reconciled live evidence

Live isolation run `gpu-isolation-live-a` passed positive host-listener control followed by offline rejection, private HOME/credential-environment removal, readonly source/experiment/root write rejection, writable output, only /dev/nvidia1 visible, independent numerical reopen, and three numerical-tamper rejections. Independently reopened all output and current code hashes, matched computation receipt linkage and runtime identity, and promoted `research/gpu-runtime-verified.json`. Ticket 08 is verified complete for single-device Torch runtime readiness; no custom sparse extension, multi-GPU or model quality claim follows. Camera label audit session 77207 remains live.

### Camera cohort and semantic diagnostic evidence

Session 77207 completed all 18 coverage-screened validation scenes for both segmentation families. Reconciled all 36 generation/HDFS/semantic-count records; all 18 have positive native semantic support. Selected the first 16 under the predeclared SHA256 order and retained two reserves plus full audited denominators in `research/camera-validation-cohort.json`. This establishes camera held-out label support but does not freeze the overall protocol or prove sensor joins. Added camera native-ID semantic diagnostics with explicit eligible mask, ignored truth ID zero, false-negative handling for predicted undefined, missing vs annotated-no-support states, and null zero-union classes. Four test cases were observed failing then passed live in CPU Insula, logged at `camera-scoring-live-a`. Official panoptic/STQ parity and broader ticket 09 remain open.

### Native default detection schema and analytic metric contract

Live `detection-contract-live-a` encoded Objects through pinned upstream metrics.proto using protoc and ran the unmodified C++ default detector evaluator. Independently derived perfect, empty, wrong-class, displaced, reversed-heading, and zero-LiDAR-point ground-truth fixtures all matched vehicle LEVEL_1/LEVEL_2 AP/APH expectations within 1e-6. Both detection and segmentation binaries passed ldd dependency resolution with no TensorFlow link, and Python TensorFlow import discovery remained absent. Independently reopened artifact/verifier hashes and parsed expected metric values separately; recorded `research/native-detection-contract-verified.json`. Ticket 09 remains open: real prediction exports, complete configuration/namespace contracts and further segmentation/camera requirements still need evidence.

### Native segmentation export and metric fixtures

Inspected unmodified segmentation C++ tool: TOP and both returns only, semantic MatrixInt32 values, undefined GT excluded, undefined predictions count false negatives, absent classes receive IoU 1. Found unsafe decompression error handling and unchecked nested MatrixInt32 parse; future adapter must validate before invoking native tool. Live fixtures encode semantic matrices through pinned protoc, zlib-compress them, embed bytes in native SegmentationFrameList, then invoke native C++ metrics. Five perfect/undefined/wrong-class/ignored-GT/absent-class cases passed with independent expectations. Fresh `segmentation-contract-live-b` captures UTC, command, runtime, hashes and duration. Independently reopened code/output hashes and parsed mean-IoU expectations; recorded `research/native-segmentation-contract-verified.json`. Ticket 09 remains open for real source exports, strict payload prevalidation and complete class/configuration contracts.

### Strict structured semantic exporter integration

Added `pipeline.segmentation_export` accepting explicit context/timestamp and both ordered TOP semantic vectors. Validates native integer IDs 0..22 (rejects bool/float), frame keys, vector limits, both-return presence and duplicate keys before protoc or compression. Tests observed failing then passed. Live `segmentation-export-live-a` passes validation tests, encodes 22/44 point analytic returns via pinned protobufs and zlib, and scores the emitted artifact through native C++ at mean IoU 1. Independently reconciled candidate/output hashes and scorer output; recorded `research/structured-segmentation-export-evidence.json`. This is a guarded structured exporter, not an arbitrary compressed-blob evaluator. Real source point-identity preservation remains an open ticket 09 gate.

### Full real engineering-slice semantic export in progress

Prepared all 60 labeled engineering frames and both TOP returns (120 records) from independently validated M3 reconstruction, preserving native point order, semantic channel 1 (channel 0 is instance), frame/return IDs and source/pixel/semantic hashes. Initial preparation referenced a nonexistent `semantic` NPZ field; inspecting sensor_records established the stored Nx2 `segmentation` array, and the corrected live preparation passed. Export session 24200 terminated successfully: structured vectors encoded into native compressed MatrixInt32/SemanticFrameList. Independent wire decoder session 41750 is live: decodes native outer protobuf, checks ordered frame keys, bounded-decompresses each return, decodes inner protobufs and compares every semantic value and dimension with the prepared vectors, then runs native self-score. This is evaluator label replay, not trained predictions or a scientific result. UTC/candidate/runtime receipt capture for this full real-data route still requires a replay runner; do not close ticket 09 from these partial logs.

### Real semantic route receives complete replay evidence

Fresh runner `evaluation/verify-real-semantic-export.py` executes preparation in locked CPU Insula, export and independent wire decoding/scoring in locked metrics Insula. `real-semantic-live-b` passed all three stages for all 60 labeled frames/120 TOP returns/9,726,038 points, capturing exact commands, UTC, runtime/code/source hashes, elapsed time, peak child RSS and output bytes. A separate live source checker reopened every relevant NPZ, compared native semantic channel 1 against prepared vectors and validated original range-pixel hashes and both-return/frame identities. Independently reconciled artifact/current code hashes; recorded `research/real-semantic-export-verified.json`. Added `evaluation/contracts.json` with source-hashed native class namespaces and implemented metric settings; no implicit cross-taxonomy mapping. Ticket 09 remains open, especially real detection exports and complete mapping/configuration checks. No model training results are implied by ground-truth self-replay.

### Guarded detection export implementation

Inspected native LiDARBoxComponent Parquet schema in the acquired slice: box centers/sizes/heading, coarse class, identity, point counts and nullable detection difficulty. Initial schema probe assumed `/source/lidar_box`; corrected to native slice `/source/raw/validation/lidar_box` after observing actual layout. Added `pipeline.detection_export`, preserving frame/object identities and native 7-DoF dimension ordering. Tests observed failing then passed for valid preservation and invalid geometry/category/score/unknown-NLZ/count/difficulty/timestamp cases. Export requires explicit NLZ overlap and does not derive a polygon overlap claim. Live analytic exporter/scorer receipt capture is running under session 99557 in the locked metrics rootfs. Real detection source replay remains open; annotation metadata remains evaluation-only.

### Full real box export in progress and enum validation correction

Added float difficulty rejection after a failing regression test demonstrated that enum value 1.0 was previously accepted by equality. Fixed with explicit native integer type requirement; test passes. Preparation in live CPU Insula read all 38,363 native boxes from the two engineering segments and preserved geometry, native frame/object IDs, point counts and nullable difficulty. Export session 46988 is live: structured guarded exporter creates native GT and evaluation-only prediction artifacts, independently decodes frame/object identities and numeric fields, then self-scores positive-point targets through native C++ LEVEL_2 metrics. NLZ=false is explicitly a ground-truth replay fixture flag, not a claimed production box/polygon overlap computation. Direct Parquet reconciliation, production NLZ and resource-complete fresh replay remain open.

### Real detection source reconciliation and supported NLZ path

Session 46988 terminated successfully: real native export independently decoded all 38,363 objects and native self-replay returned LEVEL_2 AP/APH 1 for populated classes. Separate live CPU checker session 83867 reopened all native Parquet rows, exactly reconciled frame/object key sets, 7-DoF dimensions, classes, point counts and nullable difficulty. Both receipt/artifact hashes and prepared-input linkage independently reconciled in `research/real-detection-export-verified.json`; resource-complete combined replay remains open. Primary Waymo Perception documentation (https://waymo.com/intl/es/open/data/perception/, sections 3D Lidar Labels and Lidar Data) explicitly permits NLZ overlap checking against annotated points from both returns and defines flag +1=in / -1=out. Added evaluation-only `pipeline.nlz_overlap`, requiring all five sensors/two returns, aligned finite XYZ and known flags; rotated closed-box containment respects vehicle geometry. Live fixtures observed failing then passed for rotated boxes, second-return overlap, non-NLZ points, missing returns and unknown flags. Real sensor integration and full candidate-specific receipt still pending; no polygon availability assumption is needed for this documented point-based path.

### Full real NLZ integration and independent check in progress

Live producer `real-nlz-live-a` completed all 38,363 engineering boxes, loading all five sensors/both returns per frame from M3 artifacts, verifying per-artifact hashes and rejecting unknown flags. Captured full runtime/code/source hashes, UTC and resource report. Independent session 97210 is live: reopens native point flags, transforms every NLZ point into every box with an independently constructed inverse homogeneous matrix, and compares every output flag. No producer overlap helper is imported. The method inherits M3's documented TOP compensation and uncompensated non-TOP reference limitations; flags remain evaluation-only.

### Native NLZ metric suppression verified; camera coverage running

Fresh `detection-contract-live-b` passed all eight analytic native protobuf/C++ fixtures, adding a paired false-positive control: one correct prediction plus a far unmarked false positive yields AP/APH 0.5; marking only the far prediction NLZ yields AP/APH 1. Independently parsed both difficulty-level outputs and reconciled artifact/verifier hashes; recorded `research/native-nlz-metric-contract-verified.json`. This explicitly covers the positive-NLZ evaluator behavior absent from the two engineering scenes. Camera semantic source probe session 11215 is live over all 990 native PNG labels and 1,985 camera observation keys, recording native class/support masks, annotation-missing denominators, self-replay IoU and resource usage. Independent camera source reconciliation is still required.

### Full camera source evidence independently reconciled

Live checker `real-camera-source-check-a` reopened all 990 native panoptic PNG rows and all 1,985 camera observation keys. Independently derived eligible counts by panoptic >= divisor (rather than scorer support helper), native class sets, image dimensions, unique keys and missing-annotation denominator. Matched 2,133,338,748 eligible pixels and 995 missing annotations. Producer source hashes and both receipts/artifacts reconciled in `research/real-camera-semantic-verified.json`. Ticket 09 now records the implemented contracts and remaining consolidated current-candidate/dependency/resource audit; it remains open. No official panoptic/STQ parity or model-quality claim follows.

### Current evaluator boundary audit; failed broad invocation retained

Broad discovery inside locked CPU Insula ran 67 tests but failed two host GCS bootstrap tests (curl unavailable) and six host-evidence M0 tests (private HOME hides cache), with one optional host-runtime skip. These are invocation-context failures, not successful gate evidence, retained in `evaluator-audit-live-a/tests.log`. Host suite initially failed a subprocess selecting system Python without pyarrow; corrected PATH to the same probe-venv interpreter and all 67 tests passed without skips. Dedicated live evaluator suite passed 15 tests with zero skips, including current float-enum rejection, semantic/detection export boundaries, parser failure handling, camera coverage diagnostics and NLZ fixtures. Recorded code/log hashes and both failed invocations in `research/evaluator-current-boundary-audit.json`. Ticket 09 remains open for consolidated current-candidate/resource/receipt reconciliation; no host-only success substitutes for live integration.

### Resource-measured detection replay and consolidated audit running

Fresh `real-detection-live-b` captured current exporter/wire-check candidate hashes, exact command/UTC, elapsed time, peak child RSS and output bytes; all 38,363 boxes and 34,630 positive-point replay predictions decoded/scored successfully. Exported all-false NLZ flags were checked against the independently reconciled real-scene flags. Consolidated auditor verifies 11 receipt artifact/code identities, runtime contents, pinned class/configuration source hashes, live boundary suite and both native binary dependency closures, plus real route resource reports. First audit failed because the selected-file source checkout has no HEAD. Observed FETCH_HEAD is the exact pinned 99a4cb3... commit; corrected auditor now additionally compares contracted files directly with that commit's Git blobs. Corrected audit session 4034 is live; do not close ticket 09 until it completes and independent final requirement reconciliation passes.

### Ticket 09 verified complete

Corrected consolidated audit `perception-gate-audit-b` passed. Independently reopened its receipt, all 11 linked receipt/artifact hashes, current audit code, native GTest reports, all 32 published native AP/APH fixture expectations, and separate class-ID semantics (box ID2 pedestrian, LiDAR ID2 truck, camera ID2 car). Mapped every one of ticket 09's seven acceptance criteria to source-backed contracts, analytic fixtures, full real source reconciliations, live boundary/dependency checks and measured resource reports. Promoted `research/perception-evaluators-verified.json`; ticket 09 and index now verified complete. Scope remains default native 3D AP/APH, TOP semantic IoU and explicitly nonofficial camera semantic diagnostics; camera 2D/LET/STQ and cross-modal ontology require later task-specific gates. Core research is not complete and no model outcome has been claimed. Next readiness work is ticket 07: full scientific sensor manifests/joins, explicit numerical protocols/budgets, followed by baseline implementations.

### Scientific source acquisition begins

Recorded `scientific-acquisition.candidate.json`: union of 64 train, 8 development, 16 native LiDAR validation and 16 coverage-selected camera validation scenes is 103 unique contexts, with all 17 component families (1,751 expected shards). Generation-pinned acquisition session 90362 is live via `acquire-scientific-cohort.py`; do not restart while live. Keeps the two engineering scenes locally and stages exactly one raw payload at a time: deletes the upload source before HDFS download-back, so combined retained engineering bytes plus staged source stays within the 2GiB cap. Larger-than-remaining-cap objects fail without dropping scenes. Mirrors never overwrite conflicting existing data; successful download-back SHA proves existing or newly uploaded content. Each completed object runs key-only native Parquet inventory in locked CPU Insula, rejecting duplicate identities/wrong segments and recording frames/schema/key hashes; large sensor payload columns are not loaded by inventory. Inventory fixtures were observed failing then passed live. Compact completion records live under `~/.cache/waystone/waymo-perception/scientific-source-audit`; protocol/ticket 07 remain open until full cohort manifests, joins, statistics and resource protocols are verified.

### Scientific acquisition advances and partial frame-key reconciliation

Re-polled live acquisition session 90362; it continues verified HDFS/native inventory work. Independently validated completed receipt records for selected scene/component membership, official partition, pinned generations, source/download-back SHA equality, current inventory code identity and combined raw capacity. Recorded bounded partial snapshot `research/scientific-source-acquisition-progress.json`. For scenes with all 17 components present, separately reconciled full LiDAR/camera/projection/pose frame sets and every annotation timestamp subset in `research/scientific-frame-join-progress.json`. These are partial progress records, not full scientific data or protocol acceptance. Acquisition handle remains authoritative; do not restart while live.

### Paired segment statistics and training support audit

Acquisition session 90362 remains live, now well beyond initial shards. Audited all 64 training segmentation coverage records; native motorcyclist ID5 has only eight annotated label elements. Recorded `research/training-semantic-label-support.json` with all training-only class counts and an explicit requirement to reconcile final measured-point support. Added native LiDAR semantic aggregation with undefined-GT ignored, undefined predictions as false negatives and zero-union class IoU1. Paired bootstrap resamples whole segments with the same draws across seeds/treatments, reports paired seed effects and 95% quantiles, and rejects changed eligible class support; caller must independently verify point identities. Three fixtures were observed failing then passed live and captured in `segment-statistics-live-a` receipt. Added two independent hand-derived regressions demonstrating heterogeneous-segment uncertainty and shared-seed draws; all five passed live. The expanded test file changes candidate identity relative to the original three-test receipt; a new promoted receipt is needed before claiming this complete statistical milestone. Ticket 07/protocol freeze remains open.

### Scientific acquisition/key audit and PointPillars contract preparation

Re-polled session 90362 and confirmed it remains live. Snapshot at 2026-09-30T09:12:07Z contains 258/1,751 selected source records, 15/103 complete scenes and 9,143,333,089 source bytes mirrored with recorded download-back verification. Rechecked manifest membership, exact generations, current inventory code identity, source/HDFS SHA equality and combined raw capacity. All 15 complete scenes pass frame-set equality, five-sensor aggregate row counts, calibration counts, annotation timestamp subsets and LiDAR/projection native-key digest equality. Payload alignment, sensor enum validity and final independent replay remain open; these snapshots do not close ticket 07.

Background primary-source research produced `pointpillars-implementation-contract.md`, pinned to author revision 449c7c0d081eaad44f08159f64af26d2a59f1f4c. Updated ticket 10 with explicit analytic/live PFN, padding, scatter, anchor coding/assignment, loss and NMS checks, plus a separately named common-head bridge to isolate encoding effects. No upstream installation or model training was performed. Protocol 07 must freeze dataset adaptations before execution.

### Bounded scientific preprocessing implementation plan

Acquisition session 90362 was re-polled live and continues beyond the 15-scene snapshot. Added `docs/superpowers/plans/2026-09-30-scientific-scene-preprocessing.md` with six verifiable tasks: immutable source admission, component sidecars, native sensor reconstruction, independent scene checks, HDFS publication/replay loader and full-cohort evidence. It separates one-object raw staging from decoded derived sidecars; retains the 2 GiB combined raw cap and proposes a pilot-validated 15 GiB derived working set. It explicitly prohibits concurrent raw staging while acquisition owns the capacity, and does not close protocol 07 or authorize training. Current on-disk staging count/bytes were checked against the retained engineering slice and combined raw cap.

### Live scientific admission implemented

Added pure `pipeline/scientific_admission.py` with immutable scene/component/split/generation/source-HDFS identity checks and combined raw-capacity admission. Five tests were first observed failing live because the module did not exist, then passed live after implementation. Fresh `scientific-admission-live-a` reran the five tests and admitted all 19 currently complete actual acquisition scene inventories. A separate host check compared every emitted component record and split with the staged input; final audit rehashed receipt, current candidate/tests, outputs and all 323 referenced source records. `research/scientific-admission-evidence.json` links scoped evidence and resources. This proves provenance admission only; transfer admission, exclusive shared staging ownership, payload processing and protocol freeze remain open. Acquisition 90362 remains live; no training was started.

### Live source-byte integrity verifier

Re-polled acquisition 90362 live; it continues processing selected training scenes. Added `pipeline/source_integrity.py`: bounded streaming size/SHA256/GCS-MD5 verification before payload decoding, positive-size/valid-hash admission, safe regular-file opening with symlink rejection and file-change detection. Two adversarial test groups were observed failing live before the module existed, then passed after implementation. Fresh `source-integrity-live-a` reran tests and checked all 34 retained engineering raw objects (1,200,154,353 bytes) in the locked CPU runtime; a separate host pass reopened all actual inputs with stdlib file_digest and compared emitted identities to the immutable dataset lock. Rehashed current code/tests/input-manifest/output/receipt before recording `research/source-integrity-evidence.json`. This supplies a preprocessing integrity component, not scientific transfer-locking, payload processing or protocol completion.

### Decoded native sidecars verified on a real scene

Implemented `pipeline/scientific_sidecars.py` and independent `pipeline/scientific_sidecar_validate.py`. Producer fixtures failed before implementation then passed live; checker fixtures likewise failed before implementation and now reject scalar/key/array mutations even when artifact hashes and byte declarations are updated. Fresh `scientific-sidecars-live-a` ran five fixtures, decoded every row of seven full component tables for retained engineering context 5847910688643719375_180_000_200_000, then mounted producer output read-only for an independent live source checker. Reconciled 20,495 rows and 2,238 shaped arrays exactly against native Parquet, including dtype/null fields, source/schema/artifact hashes and cumulative output byte accounting. Total evidence directory is 7,105,788,537 bytes; component working set fits the proposed 15 GiB cap. Final host audit rehashed current candidate files, all emitted artifacts and receipt; `research/scientific-sidecars-evidence.json` records scope/resources. Plan now names decoded JSON/NPZ sidecars instead of Arrow copies, preserving native arrays for bounded consumption. Scientific HDFS staging, full scene reconstruction through sidecars and protocol freeze remain open. Acquisition 90362 remained live in this turn.

### Verified bounded sidecar reader and full native replay

Added `pipeline/scientific_sidecar_reader.py`, restoring native-compatible flattened NumPy values, original shapes and null markers one row at a time. It requires independently supplied manifest identity, validates manifest and per-record hashes, native key conservation and duplicate/undeclared/unsafe artifacts. Three fail-first live test groups now pass, including changed manifests/artifacts and native key/path mutations. Fresh `sidecar-reader-live-a` then exhausted all seven pilot component tables with read-only sidecar mounts and directly compared all 20,495 returned rows to original Arrow/Parquet fields and array dtypes. Final audit verified current reader/test hashes, outputs, prior independent producer receipt and all seven manifest links. `research/scientific-sidecar-reader-evidence.json` records exact commands and resources. Updated reconstruction interface in the plan to require verified manifest hashes explicitly. Acquisition 90362 was re-polled live and continues. Full reconstruction through sidecars, scientific HDFS replay and protocol freeze remain open.

### Complete scene reconstruction through verified sidecars

Implemented `pipeline/scientific_reconstruction.py` with independently supplied component manifest hashes, complete five-LiDAR/frame/projection coverage, mandatory TOP pixel pose, explicit absent-return records, original pixel/target gathering, cursor exhaustion and combined sidecar/output capacity admission. Three fixture groups failed before implementation then passed live; they pin TOP world/reference translation analytically and check both returns, missing supervision, absent returns, incomplete sensors and budget rejection. Fresh `scientific-reconstruction-live-a` reconstructed all 198 frames / 1,980 sensor-return records / 36,214,548 valid points for the first engineering scene through the decoded sidecars. Separate live checker used read-only producer and independently verified M3 reference mounts and compared every artifact identity, coverage field, array value and dtype; all matched exactly. Combined derived working set is 10,480,270,573 bytes, below proposed 15 GiB cap. Final audit rehashed all current candidate files, emitted artifacts, linked sidecar/M3 receipts and reference manifest. `research/scientific-reconstruction-evidence.json` captures exact commands, resources and scoped validation. Acquisition 90362 was confirmed live; scientific HDFS publication/replay, full cohort processing and protocol freeze remain open. No model training occurred.

### Deterministic scene archive and real HDFS round trip

Implemented immutable deterministic USTAR scene packaging and a separate streaming member checker. Producer/checker tests failed before implementation then passed live. `scene-archive-hdfs-live-a` packaged the independently verified real engineering scene (1,981 members; 3,376,015,360 bytes), uploaded without overwrite through Waystone to an engineering-only content-addressed HDFS path, deleted the local upload archive before download-back, checked size/SHA, and independently validated every downloaded canonical member live. Publication manifest was uploaded only after validation and downloaded back with exact hash equality. Packaging working set is 13,856,285,933 bytes; final audit also counted metadata/log/receipt files within the 15 GiB cap.

A new dot-dot-only member regression exposed a missing path rejection; observed live failure, fixed the checker, then ran current fixtures and the full already-downloaded archive in `scene-archive-current-check-b`. Current checker rejected all corrupt/missing/duplicate/path/link/noncanonical-time cases and validated all 1,981 real members. Historical publication manifest/code identity is preserved, with current checker receipt linked separately. Final audit rehashed current producer/checker candidates, both receipts and every linked artifact, including archive and publication download-back. `research/scene-archive-hdfs-evidence.json` and updated progress snapshot record exact HDFS URI, commands, resource measurements and engineering-only scope. Scientific publication/replay loader, full cohort processing and scientific protocol remain open; no model training occurred.

### Verified archive dataset reader and two independent full replays

Implemented `pipeline/scientific_dataset.py` and durable verifier `verify-archive-dataset.py`. The loader requires an externally verified publication identity, verifies the full canonical archive before yielding records, checks engineering/scientific role membership, complete frame/sensor/return inventory, payload identities/shapes and resident record byte limits. Returned records separate physical observations, native identities/pixels, segmentation targets, evaluation-only NLZ and stored camera correspondence; no unpacked scene cache is created. Initial three test groups failed before implementation then passed live. Real replay exposed two incorrect assumptions: projections are native float32 arrays with integral values, and instance -1 accompanies valid stuff semantics. Diagnosed both against actual source arrays, added regressions that failed live, and fixed value validation while preserving original dtypes and all semantic support. Historical failed replay logs remain in scientific-dataset-live-a/b.

Fresh `scientific-dataset-live-c` passed all five current fixture groups, then ran two separate full live reader replays with downloaded archive/publication and verified reference point records mounted read-only. Each returned 1,980 records and 36,214,548 points; every array and dtype matched original source artifacts and both native-identity/array digests agreed. Final audit rehashed current loader/checker/verifier/test code, all receipt artifacts and linked publication/reference identities. `research/scientific-dataset-evidence.json` records exact reproducible commands and resource costs. This establishes the engineering archive loader; scientific source staging, full-cohort processing, detector box/camera input assembly and protocol freeze remain open. No model training or improvement claim occurred.

### Exclusive raw staging and live duplicate-launch rejection

Implemented `pipeline/staging_lease.py` with a nonblocking kernel flock, regular-file/no-symlink lock admission, automatic release on exceptions and authoritative same-user live process detection for acquisition started before lease support. Three fixture groups failed before implementation then passed live inside the locked CPU runtime, including actual separate-process exclusion and a real legacy-script fixture held live on stdin. Added the lease to future `acquire-scientific-cohort.py` launches; the already-running acquisition was neither stopped nor restarted. `staging-lease-live-a` reran all fixtures and attempted a second actual host acquisition launch while the original PID was confirmed live: the second launch exited with the expected ownership refusal before transfer, while the original remained present. Final audit rehashed candidate/tests/acquisition entry, live logs and receipt. `research/staging-lease-evidence.json` records scope/resources. Scientific preprocessing must use this same cache-level lease; actual staged-source processing and protocol freeze remain open.

### Bounded staged-source transfer lifecycle

Implemented `pipeline/staged_source.py`: shared raw-staging lease, orphan-stage refusal, combined retained/raw admission, structured Waystone get, inherited RLIMIT_FSIZE bounded by remaining raw allowance, source size/SHA256/GCS-MD5 verification, and owned temporary cleanup after success or any consumer/transfer failure. Source inspection of Waystone confirmed single-get temporary download followed by rename; the sibling repo was not modified. Three fail-first test groups now pass live, using controlled transfer processes to prove verified bytes, lifecycle cleanup, corrupt transfer rejection, actual oversized writes bounded by the kernel, and before-transfer rejection of insufficient capacity/orphan staging. Fresh `staged-source-live-a` reran tests and attempted production staging against a completed native source record while acquisition PIDs were confirmed live; it refused before transfer and left acquisition running. Final audit rehashed current stager/dependencies/tests, logs and receipt. `research/staged-source-evidence.json` explicitly scopes this to live controlled transfers and the real acquisition guard; authenticated production HDFS source processing remains unproven until the owner finishes. Protocol 07 and all model work remain open.

### Scientific component command and guarded preprocessing orchestrator

Added `pipeline/scientific_component.py` with separate offline decode/validate commands. Its command-boundary test failed before implementation, then passed live; independently detects a corrupted emitted metadata artifact and leaves no successful checker report. Added `scientific-preprocess.py --scene SCENE --output DIRECTORY [--component TAG]`: admits all 17 source records, excludes engineering scenes, refuses live acquisition before output creation, uses bounded shared-lease HDFS staging, runs separate locked producer/checker stages with decoded sidecars mounted read-only for checking, hashes source/candidate/runtime/artifacts and validates exact resume identities. Layout is `sidecars/COMPONENT` plus `evidence/COMPONENT`, matching reconstruction input. Unpromoted partial candidates are preserved and refused rather than overwritten. Resume and authenticated scientific processing are not yet live-verified.

Fresh `scientific-component-live-a` passed the CLI fixture and separately decoded/checked all five native LiDAR calibration rows plus all 198 native vehicle-pose rows from the retained engineering scene. It then invoked the real scientific orchestrator against a complete training scene: ownership guard refused before any processing output or transfer while acquisition remained live. Final audit rehashed current entry/worker/test, every artifact and receipt. `research/scientific-component-evidence.json` scopes this to native component command integration and the guard; full scientific scene processing remains open.

### Annotation timestamp alignment and independent task support

Added pure `pipeline/supervision_alignment.py`: separate native point-semantic targets, camera mask targets, camera measurement availability and joint annotation timestamps. Four fixture groups failed before implementation then passed live; disjoint camera labels cannot reduce point evaluation support, missing camera measurements are explicit, and absent/invalid/duplicated frame catalogs reject. Fresh `supervision-alignment-live-a` ran the fixtures and 69 currently available native scene catalogs inside locked Insula; a separate host set-algebra check reconciled every emitted catalog with immutable acquisition records. All 2,056 LiDAR-labeled timestamps have camera observations, while only 173 have both point/camera labels; camera mask target catalogs contain 1,157 timestamps. Final audit rehashed current code/tests, all 207 linked source records, staged inputs, logs, outputs and receipt. `research/supervision-frame-alignment.json` retains 34 pending scenes and explicitly scopes this to timestamp catalogs. Per-camera validity and valid-point/pixel support remain payload checks. Primary point-mask transfer retains native point supervision plus permitted camera measurements; camera panoptic GT supports its separate mask evaluation rather than defining an accidental joint-label subset. Acquisition remained live; scientific protocol remains open.

### Expanded live supervision-clock audit

Insula supervision-alignment-live-b independently checked 75 available scene catalogs; 28 remain pending. Native point targets: 2228; camera-conditioned point frames: 2228; jointly annotated timestamps: 178. All source-record identities and current inventory/module hashes were checked. This is timestamp evidence only; scientific protocol and native payload gates remain open. Acquisition session 90362 was confirmed live and was not restarted.

### Independent staged-source scene checker

Added `pipeline/scientific_scene_validate.py` and replay command `python3 experiments/waymo-perception/verify-scientific-scene.py OUTPUT_DIRECTORY`. Fail-first fixtures cover rehashed pixel/physical/NLZ/projection/semantic/coordinate corruption, changed source and sidecar provenance, return identity, missing/extra artifacts, motion and presence, and point-count changes. Real run a rejected the checker’s incorrect native-dtype assumption for physical features; a float32 regression reproduced it before fixing the checker to require the existing lossless float64 promotion. Failed evidence remains unpromoted.

Successful `scientific-scene-validation-live-b` independently reconciled all 1,980 records, 198 frames and 36,214,548 native points. Exact original pixel/target order and target dtypes were checked; physical values were checked against lossless float64 promotion. Independent scalar equations sampled up to 17 rays in every nonempty record, maximum error 1.24344978758e-12 m. Seven live test groups passed (including three reconstruction fixture groups). Elapsed live verification 31.243 s; peak child RSS 48620 KiB. Linked receipts, current candidate hashes and emitted artifacts were independently rehashed after completion. This is engineering preparation, not scientific-cohort publication or ticket 07 closure.

### Separate scientific scene command boundary

Added `pipeline.scientific_scene_command` producer/checker modes with externally supplied trusted sidecar manifest hashes. A missing-module failure was observed before implementation. `scientific-scene-command-live-a` then passed four live fixture groups, including the existing three reconstruction fixture groups and a separate-subprocess integration test: reconstruction, successful independent receipt, existing receipt overwrite refusal, changed source identity refusal and no failed check receipt. Current command/dependency and evidence hashes were independently audited. Scientific host transfer/full-scene orchestration and publication remain open; acquisition session 90362 was freshly polled live and not restarted.

### Scientific reconstruction orchestration preparation

Added receipt-anchored `verified_sidecar_hashes` after observing the missing-module failure. Two live test groups cover admitted provenance and seven changed/missing/failed-evidence cases. Connected `scientific-preprocess.py --reconstruct` to sidecar admission, one staged LiDAR source, separate read-only sidecar/point checker mounts, independent native source reconciliation and source/candidate/runtime-bound scene resume. `scientific-preparation-live-a` records current code hashes, live fixtures and the actual reconstruction-mode CLI refusing confirmed live acquisition PID 3136522 before output creation or transfer. Full scientific source transfer, host reconstruction integration, resume and immutable publication remain unverified. This is aligned preparation and does not close ticket 07.

### Scientific publication identity contract

After a fail-first missing-module run, `scientific-publication-contract-live-a` passed two live fixture groups covering publication metadata and eight failed/mismatched identity cases. The contract preserves all 17 original source generations/hashes/HDFS identities and scientific partition membership, requires independent scene/archive identities plus mirror SHA agreement, and emits an immutable hash-keyed scientific archive URI. It performs no transfer and requires callers to verify supplied receipts first. Receipt, current code/test hashes and artifacts were independently rehashed. Scientific transfer/publication/replay remain open. Acquisition session 90362 was freshly confirmed live and left running.

### Scientific split replay gate and fresh complete engineering replay

Added legal scientific train/development/validation/camera-validation combinations and cross-usage rejection tests. The duplicate scientific split fixture failed live because `[train, train]` was accepted; the loader now requires a nonempty list of distinct string memberships before enforcing official/research partition legality. `scientific-dataset-live-d` passed all seven fixture groups and two complete independent replay checks, each 1,980 records/36,214,548 points, with identical original identity/array digests. Current code, receipt identity and every captured artifact were rehashed after completion. This is scientific split contract evidence plus engineering-data replay, not scientific-cohort publication or training. Acquisition session 90362 remained live; a filesystem-only progress count showed 1,471 of 1,751 source receipt files and 86 complete scene inventories. Counts are not final source acceptance.

### Acquisition receipt identity reconciliation

Reconciled 1489 existing source receipt identities against exact cohort/component membership, official/research partitions, generation-pinned source URI, HDFS target, mirror SHA, current native inventory code and successful live inventory log. 262 source objects remain pending. Per-record hashes and missing identities are recorded in `research/scientific-source-identity-progress.json`. This is a partial receipt audit, not full payload replay or final source acceptance. Acquisition session 90362 was freshly polled live.

### Expanded native sensor-frame inventory reconciliation

Checked 87 available scenes / 17211 native frame timestamps against camera-image, LiDAR, camera-projection, TOP-pose and vehicle-pose inventories. All matched timestamp catalogs and required row counts. 16 scenes remain pending. Per-source receipt hashes are stored in `research/scientific-sensor-frame-progress.json`. This checks frame catalogs/counts only; exact sensor enum membership and source payload/geometry checks remain live scene gates. Acquisition session 90362 was freshly confirmed live.

### Orphan geometry sidecar regression

Three live fail-first cases demonstrated that the independent scene checker accepted extra pose/projection/segmentation identities outside the native frame set. The checker now independently requires exact TOP-pose and all-sensor projection catalogs, and TOP-only in-scene segmentation support. Eight live fixture groups passed. Fresh full-scene verifier session 13060 was launched as `scientific-scene-validation-live-c`; completion is not yet claimed here. Earlier dependent receipts remain historical evidence and must not be treated as current-code acceptance.

`scientific-scene-validation-live-c` completed successfully: 1,980 records / 36,214,548 points and maximum sampled scalar error 1.2434497875801753e-12 m. Current candidates, receipt and artifacts independently rehashed. Full scientific cohort and dependent command/orchestration acceptance remain open.

### Current scene-command receipt refresh

`scientific-scene-command-live-b` passed four live fixture groups against the stricter orphan-sidecar checker. Separate producer/checker commands, immutable successful receipt and no failed-check output were reverified. Current candidate/runtime/log/receipt identities were recorded and independently rehashed. This replaces the current command evidence link; scientific transfer/integration/publication remain open. Acquisition session 90362 was freshly confirmed live and left running.

### Complete-scene source identity snapshot

90 of 103 scenes have all 17 source receipt identities reconciled to the candidate and current inventory code. 13 scenes remain pending. Snapshot stored in `research/scientific-complete-scene-progress.json`; it does not substitute for final admission or payload validation. Acquisition session 90362 was freshly confirmed live and left running.

### Expanded live complete-scene source admission

`scientific-admission-live-b` admitted 90 complete scenes from all 17 source families; 13 scenes remain pending. A separate host audit compared every admitted source record and partition with the original candidate and rehashed all input receipts. Live runtime/code/artifact identities are recorded in the receipt linked by `research/scientific-current-admission-progress.json`. This partial source gate does not validate payload reconstruction, publication or model comparisons. Acquisition session 90362 was freshly confirmed live and left running.

### Current preprocessing gate refresh

`scientific-preparation-live-b` reverified live receipt-admission fixtures and actual reconstruction-mode ownership refusal against the current orphan-sidecar checker. Current candidate, runtime, artifact and receipt identities were independently rehashed. The live acquisition still owns staging; no second transfer or output creation occurred. Full scientific transfer, scene integration, resume and publication remain open.

### Camera-validation source receipts

4 of 16 coverage-selected camera-validation scenes have all 17 source records with matching official/research identities, source/mirror SHA and populated camera annotation inventories. 12 remain pending. Per-source hashes are recorded in `research/camera-validation-source-progress.json`. This is receipt/coverage evidence only, not spatial support or scientific task acceptance. Acquisition session 90362 was freshly confirmed live.

### Scientific raw-capacity evidence

Checked declared sizes from 1574 available source receipts against retained engineering raw plus the combined 2 GiB cap. Every available source fits within the remaining 947329295 bytes. Largest available objects are recorded in `research/scientific-raw-capacity-progress.json`; missing sources and actual staged transfers remain separate acceptance checks. Acquisition session 90362 was freshly confirmed live.

### Valid-point native semantic support

Added `pipeline.semantic_support` after observing missing-module failure. Three live fixture groups pin native ID0 masking, valid stuff semantics with instance -1, both-return accumulation, missing versus labeled-empty support, duplicate identity/non-TOP/invalid-class/point-count rejection. `semantic-support-live-a` counted 4,777,237 eligible labeled points from the complete engineering archive; a separate live checker independently read original verified point-label files and reconciled every native class histogram and per-frame count. Current candidate, receipt and artifact identities were rehashed. This engineering support report prepares scientific rare-class auditing; full scientific support and protocol freeze remain open.

### Expanded camera-validation source reconciliation

Reconciled all 17 source receipt identities for 10 of 16 camera-validation scenes, including native inventory code and exact generation URI; 6 remain pending. All completed scenes have populated camera annotation inventories. Updated per-source hashes in `research/camera-validation-source-progress.json`. This is partial receipt/coverage evidence, not source payload or scientific processing acceptance. Acquisition session 90362 was freshly confirmed live.

### Refreshed complete-scene source identities

100 of 103 scenes now have all 17 source receipt identities reconciled; 3 remain pending. Current inventory code and official/research membership match, with source/mirror SHA agreement. Updated per-record hashes in `research/scientific-complete-scene-progress.json`. This is partial receipt evidence, not payload/publication or scientific protocol acceptance. Acquisition session 90362 was freshly confirmed live.

### Acquisition terminal and first scientific preprocessing pilot

Acquisition session 90362 completed with authoritative exit code 0. Reconciled all 103 scenes / 1,751 source receipts using the current admission implementation, engineering-scene exclusion, pinned source/HDFS identities, current inventory code and successful live inventory logs. Evidence: `research/scientific-source-admission-complete.json`; this is source receipt acceptance, not scientific payload closure. Started actual first training-scene preprocessing `1730266523558914470_305_260_325_260` with `--reconstruct`, output `~/.cache/waystone/waymo-perception/scientific-processing/training-pilot-a`, exec session 35678. The pilot uses the production shared staging lease, HDFS download/source checks, seven sidecar producer/checker pairs and independent full scene reconstruction. Session 35678 was freshly polled live; do not restart while live. Publication/replay and protocol freeze remain open.

### First scientific training-scene pilot completed

Session 35678 completed with exit code 0. All seven scientific component sidecar producer/checker pairs and full native scene reconstruction/check passed live on training scene `1730266523558914470_305_260_325_260`: 197 frames, 1,970 sensor/return records and 32,547,972 points. Independent host audit session 37956 then rehashed all eight receipts, all captured artifacts, current candidates and source audit identities; it passed with final derived working set 10,038,227,794 bytes under the proposed 15 GiB cap. Evidence: `research/scientific-training-pilot-evidence.json`. A genuine resume invocation was started as session 20533; do not repeat while live. Scientific publication/replay, second camera-validation pilot, full cohort processing and protocol freeze remain open.

Resume session 20533 completed with exit code 0: all seven component resumes and the full reconstruction resume verified. Every original receipt identity remained unchanged. Publication/replay and full scientific program acceptance remain open.

### Scientific training-pilot publication started

Added `publish-scientific-scene.py` to execute the existing tested archive/publication contracts against an externally trusted independent scene receipt: rehash source artifacts/current processing candidates, live deterministic packaging, immutable Waystone put, remove only the upload archive before download-back, full live mirrored archive check, then publication manifest put-last/download-back. Started training-pilot publication as exec session 55643 with trusted reconstruction receipt SHA fc0fcef6859cf6afb243855fe9a82ab51e0a3e34371a3c76143acaa7d60bbab4. Do not restart while live. Publication output `~/.cache/waystone/waymo-perception/scientific-processing/training-publication-a`. Scientific replay and full cohort/model comparisons remain open; this archive contains decoded point records, with camera/detector task inputs requiring their separate native-key assembly.

### Scientific training-pilot immutable publication completed

Publication session 55643 completed with exit code 0. Live deterministic archive packaging, immutable HDFS put, removal of upload archive before download-back, SHA agreement, independent live canonical-member check, scientific manifest put-last and exact manifest download-back all passed. Publication receipt, all captured artifacts and current candidates were independently audited before launching replay. Evidence: `research/scientific-training-publication-evidence.json`. Added `verify-scientific-replay.py` for two separate live scientific loader passes against verified native point files. Started training replay session 51243; do not restart while live. Scientific cohort, camera/detector native input assembly, protocol freeze and model comparisons remain open.

### First scientific archive two-pass replay completed

Session 51243 completed with exit code 0. Two separate live scientific `train` loader passes each matched all original native arrays/identities: 1,970 records and 32,547,972 points, with identical replay digests. Current replay/loader candidates, receipt and every captured artifact were independently rehashed. Evidence: `research/scientific-training-replay-evidence.json`. Publication total working set was 13,060,255,069 bytes. Next scene must preserve the bounded local retention policy; publish/verify any required retained sidecars and record verified eviction before accumulating another complete scene. Camera/detector native input assembly, camera-validation pilot, full cohort protocol and model comparisons remain open.

### Verified scientific point-cache eviction

After fail-first/live eviction fixtures, actual training-pilot eviction ran in live Insula with processing/publication writable mounts and read-only replay evidence. All point payloads and the downloaded archive were rehashed before deletion; recovery manifest was written first. Removed 6041645548 locally cached bytes, preserving report, receipts and immutable HDFS recovery URI. A separate host audit verified terminal eviction status, missing only intended payloads, unchanged publication/replay receipt identities and retained point report. Evidence: `research/scientific-point-eviction-evidence.json`. Large native decoded sidecars remain local until their publication is verified. Scientific task assembly/cohort and model comparisons remain open.

### Decoded sidecar bundle preparation

Added deterministic decoded-component archive production and an independent streaming checker after observing a fail-first missing-module error. `component-archive-live-a` passed three live fixture groups: exact member/provenance retention and deterministic bytes, changed/undeclared source or unsafe path/capacity rejection before archive creation, and corrupt archive/manifest rejection. Bundle membership is anchored to externally verified file hashes; it contains only decoded component files, no raw Parquet. Combined original sidecar/archive/other bytes are admitted before serialization. Current code/test/receipt hashes were independently rechecked. Actual training-sidecar packaging/publication and verified eviction remain open before the next scientific scene accumulates locally.

### Native scientific sidecar publication started

Added `publish-scientific-sidecars.py` to connect tested component-bundle contracts to production Waystone transfers: independently trusted scene receipt, rehashed seven source component receipts/artifacts/current candidates, live deterministic bounded packaging with original generation/source provenance, immutable HDFS put, delete upload archive before download-back, full independent live bundle checking, manifest publication last and exact manifest roundtrip. Started session 88742 for the first training pilot, output `~/.cache/waystone/waymo-perception/scientific-processing/training-sidecar-publication-a`. Do not restart while live. Point payloads were already independently published/replayed/evicted, permitting sidecar packaging within the working cap. Actual bundle publication and sidecar eviction remain unproven until this session and its final independent audit pass.

### Native scientific sidecar publication independently accepted

Session 88742 completed with authoritative exit code 0. All six stages passed: live deterministic packaging, immutable HDFS put, original archive removal before download-back, independent live bundle validation, publication manifest put-last, and manifest download-back. Separate audit session 18238 rehashed current candidate code, every captured publication artifact, the trusted scene receipt, all seven component receipts, all 21,769 original sidecar files and the mirrored archive/manifest; provenance and file inventory agree. Evidence: `research/scientific-sidecar-publication-evidence.json`, publication receipt SHA b5c883426125f99eb1e9c2c88a2a95a18462339f9278dcdd628793e5ece1bce2. Recorded combined working set 14,057,765,696 bytes remains below the proposed 15 GiB cap. Verified sidecar eviction remains the next required bounded-retention action before another full scene. Scientific protocol, full cohort/task assembly and model comparisons remain open.

### Verified sidecar eviction implementation and actual run

Observed fail-first missing sidecar-eviction module, then added full trusted publication/artifact/source inventory checks before recovery-manifest-first deletion. Live fixture session sidecar-eviction-live-b passed success and five mutation cases (payload, archive, receipt, extra file, symlink), retaining failed mount-path fixture evidence separately. Evidence: `research/sidecar-eviction-evidence.json`. Actual scientific sidecar eviction started as exec session 73355 after launch-plan correctly rejected overlapping source/output mounts; no deletion occurred in the rejected launch. Active run mounts experiment read-only, processing at /outputs and publication at /opt, anchors publication receipt b5c883426125f99eb1e9c2c88a2a95a18462339f9278dcdd628793e5ece1bce2. Poll the same session; do not restart until terminal. Completion and independent post-eviction audit remain pending.

Actual eviction session 73355 completed with exit code 0, removing 14,051,493,845 verified cached bytes after recovery-manifest creation. Independent post-run audit confirmed every intended payload is absent, publication receipt identity unchanged and point report retained. Evidence: `research/scientific-sidecar-eviction-evidence.json`. Next: camera-validation pilot and remaining scientific protocol/task assembly.

### Camera-validation scientific preprocessing started

Started production `scientific-preprocess.py --scene 4759225533437988401_800_000_820_000 --output ~/.cache/waystone/waymo-perception/scientific-processing/camera-validation-pilot-a --reconstruct` as exec session 8172. Scene is the first recorded coverage-only held-out camera cohort member, with official validation / research camera_validation membership. Three native calibration/vehicle-pose components have already passed producer/checker pairs live; remaining components and full scene reconstruction are pending. Prior training payloads were verified evicted before this run. Poll the same handle, do not restart while live. Ticket 07 now links complete source admission and historical pilot/recovery evidence while retaining scientific gate open.

### Full scientific supervision frame catalogs independently verified

`supervision-alignment-live-c` re-ran existing live fixtures and derived separate frame-support catalogs for all 103 acquired scenes from 309 generation/mirror-verified source receipt identities. Independent set arithmetic checked every output list; all source receipt hashes remained unchanged. All 3,118 point-labeled timestamps have camera measurements; camera mask evaluation has 2,735 labeled timestamps and only 437 timestamps have both annotation families. Evidence: `research/supervision-frame-alignment.json`, receipt SHA 5c1e2bdbe0ce00f8a0b46fe7a876508b2ef43b722ca10892798c5cfa3b0bc327. This closes timestamp catalog audit only; per-camera pixel visibility and native point support still require payload checks. Ticket 07 updated without closing scientific protocol. Camera-validation preprocessing session 8172 remains the active same-handle workflow.

Camera-validation preprocessing session 8172 completed with exit code 0: seven component producer/checker pairs and independent full scene reconstruction passed (198 frames, 1,980 records, 34,882,229 points). Separate complete receipt/current candidate/artifact hash audit is running as session 50157; poll before accepting `research/scientific-camera-validation-pilot-evidence.json` or starting publication. No training or scientific protocol closure is implied.

Independent camera-validation audit session 50157 completed exit 0: all eight receipts, every captured artifact and current candidates rehashed successfully. Evidence: `research/scientific-camera-validation-pilot-evidence.json`. Launching immutable point publication through the production script, trusted audited reconstruction receipt; publication/replay remains open until terminal checks pass.

### Camera-validation point publication live observation

Publication exec session 58730 was freshly polled live. Deterministic archive pack passed; HDFS upload is still active and no final receipt is present. Do not restart the session. Source camera-validation pilot has already passed independent eight-receipt/artifact audit. Next action after terminal successful publication: independently rehash receipt/current candidates/artifacts, then run `verify-scientific-replay.py` using recorded externally trusted publication receipt SHA and `--usage camera_validation`; all original point payloads must remain available until two replay passes and verified eviction complete.

### Motion evaluator preparation during verified publication wait

Camera-validation publication session 58730 freshly polled live; HDFS upload still active, so no restart or replay promotion. Research skill invoked for independent primary-source Motion evaluator contract investigation; agent /root/motion_metric_contract inspects pinned WOD 99a4cb3ff07e2fe06c2ce73da001f850f628e45a native source, with output `research/motion-native-evaluator-contract.md`. No training, evaluator implementation or ticket19 closure is implied.

### Camera-validation immutable point publication independently accepted

Session 58730 completed exit 0: pack, HDFS put/download after removal of original upload archive, independent live archive check and manifest put-last/download all passed. Rehashed current candidates, all captured artifacts and trusted native scene receipt. Evidence: `research/scientific-camera-validation-publication-evidence.json`. Launching two separate scientific loader replays with usage camera_validation, original reconstructed points mounted read-only. Full cohort/scientific protocol and camera task assembly remain open.

Camera-validation publication audit and replay workflow is exec session 89300. It rehashes the complete publication before starting replay; poll the same handle until terminal. Do not evict native points or mirrored archive until replay acceptance and independent post-run audit.

### Camera-validation two-pass scientific replay accepted

Session 89300 completed exit 0: both separate live camera_validation loader passes exactly matched original native point identities/arrays for 1,980 records and 34,882,229 points; digest 0d6ea58b1173828d2f8774668bbdc279f57c0ce2e98c2db26a7dee29a3d86f62. Independent audit rehashed current candidates and all replay artifacts, confirmed publication linkage and exact repeat agreement. Evidence: `research/scientific-camera-validation-replay-evidence.json`. Actual verified point eviction started as exec session 41557, preserving recovery metadata and sidecars; poll same handle before publication of sidecars. Full scientific protocol and model comparisons remain open.

Camera-validation point eviction session 41557 completed exit 0, removing 6,501,023,684 bytes. Independent postcheck verified all intended payloads absent, point report retained and publication/replay receipt identities unchanged. Evidence: `research/scientific-camera-validation-point-eviction-evidence.json`. Launching production seven-family sidecar publication against audited reconstruction receipt; source sidecars remain resident until mirror validation and verified eviction.

Camera-validation sidecar publication is active exec session 34127; do not restart while live. Motion primary-source investigation delivered `research/motion-native-evaluator-contract.md`: pinned native dependency/API/fixture contract, with ingestion/build/evaluator parity still unverified. Review native sample ordering, validity counts and confidence semantics before implementation; no ticket19 closure or training implied.

### Camera-validation sidecar acceptance and native Motion build

Sidecar publication session 34127 completed exit 0. Independent audit session 64484 rehashed receipt/current candidates/all captured artifacts, trusted reconstruction/seven component receipts and all 39,523 original sidecar files. Evidence: `research/scientific-camera-validation-sidecar-publication-evidence.json`, receipt SHA 152c8ba1bdb195bb3a2af91fe8f5bab59568b70d88c03d4623ae820392069c33. Verified eviction launched against this trusted identity; postcheck pending. Added approved ticket19 preparation plan `docs/superpowers/plans/2026-09-30-native-motion-metric-verifier.md`. Live expected missing Motion binary failure retained under motion-native-fail-first-a. Separate motion-evaluation recipe preserves existing Perception recipe/root and immutable parent image. BuildKit could not resolve local image ID, so legacy offline builder used. Initial compile exposed missing GoogleMock linkage; bundled /usr/src/googletest source admitted without download. Corrected build session 98250 active; native live suites still unverified.

Camera-validation sidecar eviction session 85153 completed exit 0 and independent postcheck confirmed all intended payloads absent, publication receipt identity unchanged and point report retained. Removed 14,231,874,515 cached bytes; evidence `research/scientific-camera-validation-sidecar-eviction-evidence.json`. Corrected native Motion image build session 98250 completed exit 0; starting separate locked-root materialization and upstream live regression verification through `verify-motion-native.py`. Scientific model comparisons, full cohort/task inputs and Motion ingestion remain open.

Native Motion root materialization/live verification is active exec session 75877; poll same handle and do not restart while live. The runner exports the separately built image, locks content/parent/source/recipe identities, runs unchanged metric and utility GTest suites offline, checks all individual statuses, and checks absent TensorFlow/native ldd closure. Independent final receipt/artifact audit still required before evidence acceptance.

Native Motion verification session 75877 completed exit 0. Both unchanged upstream suites and dependency checks passed offline live. Independent final audit rehashed candidate/recipe/artifacts and content-verified the separate root; checked all individual GTest statuses and exact test counts. Evidence: `research/motion-native-regressions-verified.json`. This prepares ticket19; CLI/analytic parity/native scenario ingestion/causal extension checks remain open.

### Native Motion scoring boundary implementation

Added first analytic CLI fixtures after live fail-first missing-binary verification (`motion-cli-fail-first-a`): exact perfect/2m errors and measurement counts, first serialized K semantics, malformed proto/identity/endpoint fail-before-output. Separate CLI recipe inherits immutable verified Motion image and preserves prior runtimes. Wrapper reads bounded textprotos, validates shape/rate/current index/endpoints/finite inputs, calls native ComputeMetricsStats and emits native metrics plus measurement counts. Initial compile caught incorrect field spelling; corrected to pinned proto step_configurations and retained failure log. Corrected build session 18927 completed exit 0. Dedicated root materialization/live analytic and dependency checks now running as exec session 94279 using `verify-motion-cli.py`; poll same handle. Initial fixtures do not cover pooled scoring, all confidence/validity cases or acquired scenario ingestion; ticket19 remains open.

CLI verification session 94279 completed exit 0. All three initial analytic groups and TensorFlow/ldd checks passed live. Independent audit rehashed runner/test/recipe/artifacts, content-verified separate CLI root and checked actual unittest completion without skips. Evidence: `research/motion-cli-initial-verified.json`. Additional malformed/validity/confidence/group tests, pooled native scoring and actual acquired scenarios remain required before ticket19 closure.

### Expanded Motion validity/confidence fixtures

Added live tests for all-future-label missingness (zero counts, not evidence of zero error), confident wrong mode mAP 0.5 despite best-of-K FDE 0, nonfinite ground-truth velocity and reversed speed scaling. `motion-cli-expanded-red-a` ran six fixture groups: missingness/confidence cases passed, but NaN velocity was wrongly accepted (observed test failure). Added finite velocity/dimension validation to valid native states and retained old runtime as historical candidate evidence. Expanded CLI image build active session 19472; separate v2 root/runner `verify-motion-cli-expanded.py` avoids overwriting original locked root. Fresh live evidence still required.

Expanded CLI image build session 19472 completed exit 0. Separate root-v2 materialization and six-group analytic/dependency verifier launched as exec session 32283; poll same handle, then independently audit final receipt/runtime/recipe/test/output hashes before accepting expanded evidence.

Expanded CLI verification session 32283 completed exit 0. Six fixture groups and dependency checks passed live. Independent final audit verified separate root-v2 content and current runner/test/recipe/artifact identities and no skips. Evidence: `research/motion-cli-expanded-verified.json`. NaN velocity now rejects before output. Pooled scoring, joint overlap cases and acquired causal Motion ingestion remain open; no scientific forecast training/results claimed.

### Next training scene and native camera sidecar integration

Preprocessing session 75653 completed exit 0 for training scene 15036582848618865396_3752_830_3772_830: all seven component pairs and 1,980 records / 35,851,264 points independently reconstructed live. Full candidate/receipt/artifact audit passed before publication. Native camera sidecar preparation added separately after missing-module fail-first; three live fixture groups passed (exact bytes/nulls/key accounting, capacity/scene/duplicate refusal, binary mutation/extra artifacts). Actual retained engineering camera_image/camera_segmentation/camera_box producer and separate read-only checker invocations running as exec session 57772. No existing scientific preprocessing candidates were modified.

Native camera sidecar session 57772 completed exit 0: 990 camera image rows, 495 camera panoptic rows and 22,429 native camera boxes independently checked in separate live invocations. Final audit rehashed artifacts/current candidates and root identity. Evidence: `research/camera-sidecars-native-evidence.json`. This is lossless payload preparation only; image/label decoding/scientific HDFS integration/timing-resource receipt completeness remain open before research milestone closure. Next training-scene full audit/publication workflow is exec session 88203; poll same handle.

### Scientific camera HDFS orchestration

Added `scientific-camera-preprocess.py` connecting independently fixture/native-tested binary sidecars to existing all-17-family source admission, original generation/source receipt identities, raw shared lease/HDFS staging checks, separate offline producer/checker invocations and resume provenance. All scientific-processing resident bytes (including other scenes and publication archives) are counted before decoding and final receipt promotion; raw limit remains separate combined 2 GiB. Each component receipt records exact commands, UTC interval, duration/RSS, current code/root/input/output identities and independent native checks. Started actual training-scene camera_image/camera_segmentation/camera_box processing as exec session 58853 for scene 15036582848618865396_3752_830_3772_830. No existing point-processing candidates were modified. Point publication session 88203 completed exit 0; separate audit/replay workflow launched concurrently (read-only existing point payloads, no competing raw staging). Full task assembly/camera publication and protocol remain open.

Next training point publication audit/two-pass replay is exec session 81440; poll alongside scientific camera processing session 58853, without restarting either while live. Point archive and original NPZ files must remain until replay independently accepted and verified eviction completes.

Scientific camera session 58853 completed exit 0. All three HDFS-stage/producer/checker pairs passed (990 image, 100 segmentation, 9,198 box rows). Final audit rehashed each current candidate/artifact, all 17 admitted source receipt identities and verified locked root, split/timing/cap/source consistency. Evidence: `research/scientific-15036582848618865396_3752_830_3772_830-camera-evidence.json`. Original binary payloads remain locally resident; immutable camera publication/replay and decoded image/mask task alignment still open.

Point replay session 81440 completed exit 0: both passes matched 1,980 records / 35,851,264 points with identical digests. Independent receipt/current candidate/artifact audit passed. Evidence: `research/scientific-15036582848618865396_3752_830_3772_830-replay-evidence.json`. Next: verified point eviction, seven-family sidecar publication and camera-bundle publication/replay; retain original camera payloads until verified. Full cohort/protocol/model comparisons remain open.

### Next training point eviction and sidecar publication

Verified point eviction admitted against independent publication/replay receipt identities, completed live, and passed postcheck (all intended payloads absent; both receipt identities unchanged). Evidence: `research/scientific-15036582848618865396_3752_830_3772_830-point-eviction-evidence.json`. Before launching seven-family bundle publication, aggregate resident bytes across all scientific-processing outputs plus conservative USTAR/member/manifest overhead were admitted under 15 GiB, including resident camera inputs. Immutable sidecar publication now starting against trusted scene receipt; original sidecars/camera payloads remain resident until respective mirror verification/eviction.

### Camera immutable bundle publication started

Added `publish-scientific-camera.py` connecting externally audited camera evidence and three trusted component receipt identities to tested deterministic component archives, source generation/receipt lineage, aggregate scientific-working-root capacity, original-archive deletion before HDFS mirror download, independent live streaming check and metadata put-last/roundtrip. Actual publication active session 13070 for scene 15036582848618865396_3752_830_3772_830. Seven-family sidecar publication/eviction workflow remains session 61166 (point eviction already verified; pack passed). Poll these same handles; no camera or sidecar payload eviction before required checks. Camera replay/image decoding and full task/cohort/scientific protocol still open.

Both immutable bundle publications completed exit 0: session 61166 for seven LiDAR/geometry sidecar families and session 13070 for three camera families. Final independent audits rehashed current candidates, receipts, all captured publication artifacts, original component receipts and every decoded file, checking full inventory/provenance and exact manifest mirror agreement. Evidence: `research/scientific-15036582848618865396_3752_830_3772_830-sidecar-publication-evidence.json` and `research/scientific-15036582848618865396_3752_830_3772_830-camera-publication-evidence.json`. Aggregate scientific resident bytes still under 15 GiB. Next: camera-native replay/decode and verified cache eviction before accumulating another scene; full task/cohort/protocol and research models remain open.

### Camera replay and next training sidecar retention

Seven-family sidecar eviction session 91029 completed exit 0, removing 14,186,966,082 cached bytes. Independent postcheck confirmed intended payloads absent, publication receipt identity unchanged and point report preserved; evidence `research/scientific-15036582848618865396_3752_830_3772_830-sidecar-eviction-evidence.json`. Added bounded camera Dataset loader after observed missing-module fail-first; two live fixture groups passed exact binary/key/observation-target separation and publication/split/cap refusal. Actual two-pass original-sidecar comparison plus JPEG/PNG size/semantic-support decoding is running as exec session 92236 via `verify-camera-replay.py`. It mounts original references read-only, uses independently trusted publication and component receipt hashes, validates the whole bundle before yielding, and never extracts scene bytes to another cache. Poll same handle; native camera eviction/full-cohort protocol remain open.

Camera replay session 92236 completed exit 0. Both passes independently matched original 990 image/100 panoptic/9,198 box rows and decoded original JPEG/PNG dimensions and native semantic support; repeat digest/report identical. Final independent audit rehashed candidates/artifacts, content-verified runtime and checked publication linkage/repeat equality. Evidence: `research/scientific-15036582848618865396_3752_830_3772_830-camera-replay-evidence.json`. Camera verified eviction, full scientific task joins/class mappings/protocol/cohort remain open.

### Verified scientific camera cache lifecycle completed

After live fail-first and two fixture groups (successful recovery-first eviction; five mutation refusals), actual camera cache eviction completed live with exact externally trusted publication/replay identities. Independent postcheck confirmed all intended payloads absent and both receipt identities unchanged; timing/RSS/current candidate/runtime/command/log/recovery identities retained. Evidence: `research/scientific-15036582848618865396_3752_830_3772_830-camera-eviction-evidence.json`. HDFS recovery manifest retained before deletion. Next complete-cohort reconstruction scene starts only after this verified cache lifecycle; camera class mapping/task alignment and scientific protocol/model comparisons remain open.

Actual scientific camera eviction and next training reconstruction is exec session 28854. Camera eviction/postcheck completed (716,345,686 bytes removed); next scene 11343624116265195592_5910_530_5930_530 now has four component checks passed and is still live. Snapshot `research/scientific-processing-progress.json` independently rechecks replay receipt identities for all three completed point scenes: 5,930 records / 103,281,465 points. Remaining 100 selected point scenes and scientific camera/task coverage remain pending; cohort unchanged. Poll same handle before audit/publication.

### Sequential cohort driver first live lifecycle

Preprocessing session 28854 completed exit 0 for scene 11343624116265195592_5910_530_5930_530: 1,990 records / 29,019,898 points. Added `process-scientific-cohort.py` as orchestration of existing verified commands with exclusive queue ownership, exact native source/cohort admission, stage-specific receipt/artifact audits, aggregate sidecar package preflight, point/camera publication and two-pass replay, recovery-first live eviction with independent postchecks and retained per-scene checkpoint identities. First full lifecycle is running as exec session 88467, output `~/.cache/waystone/waymo-perception/scientific-processing/cohort-v1`, explicitly adopting the completed native processing directory. Do not restart or modify driver while live. Before broader unattended queue promotion, audit first complete checkpoint and strengthen successful-checkpoint resume to reconcile all current nested worker candidate/runtime identities (not just driver/source/retained receipt hashes). Full source/task/class/support/protocol/model acceptance remains open.

### First complete queue checkpoint independently admitted

Queue session 88467 and independent live checkpoint session 74045 both terminated exit 0. Rehashed live inputs/log/output/receipt, current verifier candidate, full CPU runtime content, acquisition manifest and all 17 source receipts; reran retained/nested-worker/eviction reconciliation and matched live output exactly (30 retained files, 16 worker receipts, three evictions, 49,573 evicted artifacts). Evidence: `research/cohort-driver-first-lifecycle-verified.json`; original checkpoint SHA pinned in `research/cohort-trusted-checkpoints.json` without modifying historical receipt. Scientific snapshot now four of 103 point scenes / 7,920 records / 132,301,363 points; two scientific camera scenes. Next: strengthen driver completed-scene admission using externally trusted checkpoint hashes and current nested worker/runtime checks, verify no-work resume, then remaining cohort. Protocol and all model comparisons remain open.

### Trusted completed checkpoint resume verified

Observed missing registry-admission implementation fail first, then four fixture groups passed both locally and live Insula. New `cohort_resume.py` requires an externally hash-pinned registry and invokes unchanged full nested-worker/runtime/eviction checkpoint verifier. Driver adopts old successful checkpoint only after these checks, preserving historical driver evidence. Actual scene 11343624116265195592_5910_530_5930_530 resume exited zero, performed no processing stages and preserved checkpoint SHA. Evidence: `research/cohort-resume-verified.json`. Next launch remaining 99 fresh unchanged cohort scenes; first two manual point scenes still need camera backfill. Protocol/models remain open.

Remaining 99 fresh scenes launched sequentially as exec session 64903, original acquisition/cohort unchanged, first scene 4447423683538547117_536_022_556_022. Handle confirmed live after launch; poll the same handle. Do not modify active driver or restart on observation timeout. Two prior manual point scenes need camera backfill; per-class valid-point support and scientific protocol/model comparisons remain open.

### Native Motion joint-mode boundary verified

Independent two-agent analytic fixture passed live locked Motion Insula: modes with individual errors (0,4) and (4,0) yield joint minADE/minFDE 2, averaging agents before minimizing modes; incompatible joint target-ID set refused without output. Six existing native CLI groups reran alongside two new groups (eight total, zero skips). Current receipt/candidate/log/root recipe identities independently rehashed; evidence `research/motion-joint-verified.json`. Pooled scoring, interaction/overlap coverage and acquired causal Motion ingestion still open. Cohort session 64903 confirmed live, still processing first fresh scene; do not restart or change active driver.

### PointPillars mathematical encoder preparation

Observed missing module failure live in locked Torch Insula before implementation; four analytic groups then passed live on CPU: exact nine-channel physical decorations/masked padding, nonfinite/count refusal, PFN singleton/permutation/finite gradients, XY scatter orientation/empty cells/duplicate refusal. Current receipts/candidates/log/runtime recipes independently rehashed. Evidence `research/pillar-encoder-preparation-verified.json`. Implementation keeps upstream padded-slot BN/ReLU/max policy and nine input channels; no sampling/ROI/anchor/head/training choices frozen. This is preparation only, not GPU encoder proof or ticket 10 closure. Cohort session 64903 confirmed live with first fresh point preprocess/publication/two-pass replay/verified eviction all exit zero; seven-family and camera lifecycle still active.

### PointPillars padded BN and GPU encoder parity verified

Physical GPU 1 observed idle before launch; only its device mounted in offline locked Torch Insula. Native NumPy analytic BN output/running mean/unbiased running variance matches including padded slots; padded zeros are retained after BN/ReLU and may win max. Float64 CPU/GPU PFN+scatter outputs, input and parameter gradients agree within 1e-9/1e-10. Independent current candidate/receipt/log/output/host-driver/runtime recipe audit passed. Evidence `research/pillar-gpu-verified.json`. This is analytic mathematical core only, not model training or a full-model resource estimate. Queue session 64903 first fresh full scene lifecycle completed; independent checkpoint session 13582 running.

Independent first fresh checkpoint session 13582 terminated zero; retained receipts/current workers/three recovery-first evictions reconciled live (46,049 deleted artifacts), then current evidence rehashed. Snapshot updated to five of 103 point scenes / 9,900 records / 164,789,187 points, three camera scenes. Trusted registry extended with unchanged checkpoint SHA. Queue 64903 continues remaining scenes; do not modify driver.

### Native center-Z box coding reference verified

Observed missing implementation fail-first, implemented independent NumPy metric reference, then four groups passed live locked CPU Insula: hand-computed diagonal-normalized XY, center-Z and log dimensions; additive yaw and canonical wrap; direction-bin pi correction; empty catalogs and malformed/nonpositive/nonfinite/overflow refusals. Evidence independently rehashed: `research/box-coding-verified.json`. This is an explicit Waymo center-Z adaptation, not implicit legacy bottom-Z storage. Torch head/losses/assignment/NMS and scientific protocol remain open. Queue session 64903 confirmed live; next scene 14503113925613619599_975_506_995_506 preprocessing passed.

### PointPillars deterministic assignment reference verified

Re-inspected pinned upstream target_ops.py before implementation. Observed missing module fail-first; first analytic threshold/tie test passed, then empty/no-overlap/first-target tie/malformed fixtures passed live locked CPU Insula (four groups). Final current candidate/receipt/log audit passed; `research/anchor-assignment-verified.json`. Assignments accept external overlap matrix, scalar ordered thresholds, positive GT classes, no random subsampling; forced positive ties restored after background rule, zero-overlap never forced. Similarity geometry/pruning/anchor policy/losses and scientific training still open. Queue session 64903 confirmed live with next scene point replay/eviction zero; continue polling same handle.

### Detector similarity and suppression geometry verified

Rechecked pinned source NearestIouSimilarity before implementation. Observed missing geometry module failure, passed analytic orientation/periodicity IoU; then observed missing NMS function failure and passed enclosing rectangle/tie fixture. Three complete groups passed live locked CPU Insula, including score/caps/empty/malformed handling; current receipts/candidates/log independently audited. Evidence `research/detector-geometry-verified.json`. Nearest axis alignment used for assignment; enclosing rectangles for class-agnostic suppression. Stable original-index ties are an explicit deterministic adaptation; neither is rotated 3D native evaluation. Full trainable detector and scientific protocol remain open. Queue 64903 remains active.

### Second fresh cohort checkpoint independently admitted

Scene 14503113925613619599_975_506_995_506 completed full lifecycle in queue 64903. Separate offline live checkpoint admission reconciled retained worker/runtime/source/artifact and recovery-first eviction identities; final code/log/output/input/checkpoint rehash passed. Evidence `research/cohort-checkpoint-14503113925613619599_975_506_995_506-verified.json`. Snapshot now 6/103 point scenes, 11880 records / 203150623 points and 4 camera scenes. Original selection unchanged, protocol/models open. Queue 64903 remains active; no restart or driver modification.

### Detector loss analytic reference verified

Host default Python lacks Torch, so host discovery did not establish algorithm red; reran in locked Torch Insula and observed missing pipeline.detector_loss failure before implementation. Three CPU Torch groups passed live: hand-computed sigmoid focal/SmoothL1/direction CE, ignored-anchor zero gradient and finite gradients, all-background positive-count clamp, pi yaw ambiguity remaining for direction head. Current receipt/candidate/log/runtime recipe audit passed; `research/detector-loss-verified.json`. Full trainable backbone/head, GPU model integration, frozen anchor/sampling/resource protocol and scientific training remain open. Queue 64903 confirmed live, third fresh scene point replay/eviction passed.

### Integrated pillar backbone and anchor head preparation

Observed missing model module failure in live Torch Insula; source-style three-stage 4/6/6-convolution backbone, 1/2/4 deconvolution fusion and independent class/7-residual/2-direction dense heads implemented with verified physical encoder. Live small-grid CPU forward/backward passed output cardinalities and finite gradients for every parameter. Flatten contract row(y), column(x), anchor; no label inputs. Independent current receipt/candidate/log/runtime recipe audit passed; `research/pillar-detector-preparation-verified.json`. No optimizer steps or model training performed. Native anchor generation/sampling and complete GPU/resource/export/scientific protocol remain open. Cohort queue 64903 live, third fresh scene sidecar lifecycle and camera preprocessing passed.

### Integrated GPU detector resource pilot verified

Observed physical GPU 1 idle (no compute processes), mounted only that device. Synthetic 512x512 grid, batch 1, 20,000 pillars x 32 points and source-style dense anchor head/loss passed three train-mode forward/backward calls with all parameter gradients finite; zero optimizer steps. Measured allocated peak 1,305,486,336 bytes; warm passes 0.04519/0.04478 seconds (cold 0.73401). Independent current candidate/receipt/log/output/driver/runtime recipe audit passed; evidence `research/detector-gpu-resource-verified.json`. Synthetic geometry/targets are correctness fixtures, not native training or a resource-budget freeze; native packing/I/O/optimizer/evaluator still required. Queue 64903 remains live; scene 3375636961848927657_1942_000_1962_000 full lifecycle terminal zero awaits independent checkpoint admission.

### Bounded physical pillar packing verified

Observed missing module fail-first, implemented half-open native XYZ ROI and XY cells, then three live CPU Insula groups passed. Retained original input indices survive deterministic seeded pillar/point limits; native physical dtype preserved and every clipped/dropped/retained point accounted exactly. Five-channel and nonfinite inputs refused, padding indices -1, empty catalogs explicit. Current candidate/receipt/log audit passed; `research/pillar-packing-verified.json`. No ROI/caps adopted for scientific training; native frame/GPU integration and final protocol still open. Queue 64903 remains live with fourth fresh scene preprocessing passed; third fresh complete checkpoint still awaiting separate independent admission.

### Native full-frame packing preparation verified

Rehashed trusted engineering M3 receipt and all ten original NPZ payloads for first frame (all five LiDARs/both returns), mounted source read-only, retained XYZ and physical_features intensity column 1 only (column 0 is range, column 2 elongation; NLZ remains outside features). Live packing/exact original-point identity and uniqueness checks passed: 180,827 input, 699 outside ROI, 14,384 pillars, 87,525 point-cap exclusions, 92,603 retained. Output NPZ holds original concatenated source indices; record offset map preserves frame/sensor/return lookup into original pixels. Final current runtime/candidate/receipt/output/input/log audit passed; `research/native-pillar-packing-verified.json`. Preparation receipt lacks complete timing and separate producer/checker invocation, so it does not close research milestone; actual native GPU model/resources/export still open. Queue 64903 live; independent third fresh checkpoint admission pending.

### Native measurements through complete GPU detector verified

Separate live checker reopened original ten sensor/return NPZs, verified source hashes, exact physical values/ROI/cell assignment/padding/unique indices and count caps independently of packer. Then isolated GPU1 execution admitted externally trusted packed hash and ran 14,384 actual native pillars / 92,603 retained physical points through full model/loss/backward. Every parameter gradient finite; 131,072 anchors; allocated peak 1,193,811,456 bytes; cold forward/backward 0.771887s. Explicit float64-to-FP32 model cast. Diagnostic all-background targets, zero optimizer steps, no native box supervision or accuracy claim. Independent receipt/current candidates/artifacts/driver/root recipes and checker/packed linkage audit passed; `research/native-detector-gpu-verified.json`. Scientific protocol, native target integration, actual optimizer resources and held-out training remain open. Queue64903 confirmed live; scenes337563... and681361... complete lifecycle still require independent checkpoint audits before snapshot promotion.

Independent live checkpoint admission passed for 3375636961848927657_1942_000_1962_000; current nested worker/runtime/source/retained artifacts and recovery-first eviction lineage reconciled; final candidate/input/output/log/checkpoint hashes rechecked. Snapshot now 7/103 point scenes, 231167522 points and 5 camera scenes. Evidence `research/cohort-checkpoint-3375636961848927657_1942_000_1962_000-verified.json`. Queue64903 remains active; protocol/models open.

Independent live checkpoint admission passed for 6813611334239274394_535_000_555_000; current nested worker/runtime/source/retained artifacts and recovery-first eviction lineage reconciled; final candidate/input/output/log/checkpoint hashes rechecked. Snapshot now 8/103 point scenes, 261967912 points and 6 camera scenes. Evidence `research/cohort-checkpoint-6813611334239274394_535_000_555_000-verified.json`. Queue64903 remains active; protocol/models open.

### Metric anchor lattice verified

Observed missing module failure, implemented stride-two metric center lattice and explicit [length,width,height,center_z,yaw] templates, then two groups passed live CPU Insula with hand-computed row/column/anchor flatten order and malformed grid/template refusal. Current candidate/receipt/log audit passed; `research/anchor-grid-verified.json`. Templates remain fixtures; no held-out or KITTI dimensions silently adopted. Ruling: defer training-only box-source transfers while cohort driver runs — raw staging uses nonblocking shared ownership and concurrent stats could fail the active queue — cost is later statistics collection, preserving storage and queue invariants. Queue64903 remains live; anchor statistics/configuration and scientific training open.

### Native boxes connected to full GPU backward path

Trusted engineering raw lidar_box SHA rechecked; exact context/timestamp join yields45 native rows,37 current-frame center-ROI eligible boxes. Fixture center-Z templates/thresholds create773 positive anchors, matched native categories and encoded boxes roundtrip to original dimensions/positions. Offline CPU target receipt/candidates/artifacts then isolated GPU native observation+real box target loss/backward passed every parameter finite; zero optimizer steps. Peak1,196,469,760 allocated bytes; coldforward/backward1.047427s. Final current input/output/candidate/runtime recipe/driver/target-receipt lineage audit passed; `research/native-supervised-gpu-preparation.json`. Independent native-target checker and scientific anchor configuration remain open; no training or quality claim. Queue64903live, nextscene879691...preprocessingzero; completed990914...awaitsindependentcheckpointaudit.

### Independent native box-target boundary verified

Separate offline live checker reopened original raw Arrow boxes, reconciled exact context/time/object IDs and native categories, independently decoded positive residuals to source position/dimensions/periodic yaw and direction bins, checked negative/ignored target isolation.37 represented boxes/773 positives pass; deliberately mutated center-Z target fails live without accepted checker output. Final current candidate/receipt/input/output/target-receipt lineage rehash passed. Evidence `research/native-box-target-check-verified.json` and `research/native-box-target-fault-verified.json`. This closes engineering target provenance check, not full scientific eligibility, anchor policy, optimizer resources or held-out research. Queue64903 remains live,990914...complete checkpoint pending admission.

### Native proposal decoding verified

Observed missing decoder failure, then two groups passed live CPU Insula: direction correction uses raw additive yaw before final canonical wrapping (4rad example); stable sigmoid at +/-1000, native four-class namespace, empty outputs, highest-class score, deterministic class-agnostic enclosing NMS. Current candidate/receipt/log audit passed; `research/detector-decode-verified.json`. Evaluation NLZ/point-count/difficulty metadata remains separate, no fabricated default exporter values. Model/evaluator prediction integration and scientific protocol/training remain open. Queue64903live; completed990914...checkpointawaitsindependentaudit.

Independent live checkpoint admission passed for 990914685337955114_980_000_1000_000; current nested worker/runtime/source/retained artifacts and recovery-first eviction lineage reconciled; final candidate/input/output/log/checkpoint rehash passed. Snapshot now 9/103 point scenes, 297195998 points and 7 camera scenes. Evidence `research/cohort-checkpoint-990914685337955114_980_000_1000_000-verified.json`. Queue64903active; protocol/modelsopen.

Independent live checkpoint admission passed for 8796914080594559459_4284_170_4304_170; current nested worker/runtime/source/retained artifacts and recovery-first eviction lineage reconciled; final candidate/input/output/log/checkpoint rehash passed. Snapshot now 10/103 point scenes, 334273945 points and 8 camera scenes. Evidence `research/cohort-checkpoint-8796914080594559459_4284_170_4304_170-verified.json`. Queue64903active; protocol/modelsopen.

### SAM semantic provenance gap recorded as candidate contract

Inspected pinned camera29/LiDAR23 taxonomy source locally. Coarse camera vehicle boxes cannot identify fine native point semantics; camera vegetation/sidewalk also merge tree-trunk/curb categories. Candidate contract requires identical frozen predicted camera semantic evidence across B0/B1/B2 and common independent LiDAR fallback on unknown/conflicting/ambiguous transfer, retaining all native primary points/classes. Evidence/design note `research/mask-semantic-provenance-candidate.md` linked to tickets17/18; mapping/pooling/fallback not yet frozen. This is scientific design preparation, not an implemented result.

### Conservative semantic refinement candidate verified

Observed missing mapping module failure, implemented candidate camera29-to-LiDAR23 correspondences with explicit ambiguity/undefined/unmapped reasons and unchanged full-point fallback, then three groups passed live CPU Insula. Declared annotation/coarse-box/oracle origins refused; original baseline remains untouched; unsupported/ambiguous points retained. Current candidate/receipt/log audit passed; `research/semantic-mapping-candidate-verified.json`. Origin string validation is not cryptographic provenance; learned semantic-head/checkpoint/source lineage and geometry remain required before research promotion. Correspondences remain candidate, not universal ontology equivalence or protocol freeze. Queue64903live; nextscene122579...point lifecycle passed.

### Prediction-only evaluation metadata verified

Observed missing prediction-record module failure, then two groups passed live CPU Insula: measured closed-box point count, explicit point-based NLZ with all five sensors/both returns, generated prediction anchor IDs and no GT difficulty fields; incomplete measurements refused even for empty outputs. Existing native exporter validation reused. Current receipt/candidate/log audit passed; `research/prediction-records-verified.json`. Point count is measured prediction geometry diagnostic, not claimed equal to native GT annotation point counts. All NLZ/reference limitations of existing reconstruction contract retained; real random-model export/native scoring and scientific training still open. Queue64903live.

Independent live checkpoint admission passed for 12257951615341726923_2196_690_2216_690; current worker/runtime/source/retained artifacts and recovery-first eviction lineage reconciled; final hashes rechecked. Snapshot now 11/103 point scenes, 366864446 points and 9 camera scenes. Evidence `research/cohort-checkpoint-12257951615341726923_2196_690_2216_690-verified.json`. Queue64903active. Read-only Motion source-contract investigation delegated to existing motion_metric_contract agent under research skill; no raw staging/downloads authorized for that investigation. Protocol/modelsopen.

Independent live checkpoint admission passed for 13186511704021307558_2000_000_2020_000; original source/runtime/current candidates, 30 retained files and recovery-first eviction lineage reconciled. Snapshot now 12/103 point scenes, 399146434 points and 10 camera scenes. Evidence `cohort-checkpoint-13186511704021307558_2000_000_2020_000-verified.json`. Scientific protocol/models remain open.

### Motion ingestion execution gates specified

Read the new primary-source ingestion contract and independently inspected pinned Scenario fields12/13 locally; historical/current index correspondence is explicit. Linked ticket19 to the note and specified metadata identity, bounded CRC32C framing fault checks, native extension reconciliation, future-injection rejection and actual/pooled native scoring gates. Child GCS paths remain unverified; anonymous401 is not proof existing authenticated access fails. No download or staging interference, no ingestion completion claim.

### Motion authenticated source discovery

Existing GCS credential metadata-only calls succeeded for eight v1.2.1 prefixes. Persisted bounded Objects:list JSON with object generations/checksums/sizes; validated bucket/prefix identities and absence of credentials. Scenario train/validation shards and corresponding per-scenario sensor extension directories now observed. Evidence `research/motion-authenticated-metadata.json` SHA256 d2237eb0ad151192a5c8fa767a60d1e387ff2e628095d67be0bb4e691a37ce22. Pagination retained; no complete inventory, frozen cohort, source payload download, staging lease or native ingestion claim. Ticket19 and source contract updated to distinguish this evidence from historical anonymous401.

Independent live checkpoint admission passed for 17885096890374683162_755_580_775_580; original source/runtime/current candidates and retained/evicted evidence reconciled. Snapshot now 13/103 point scenes, 439294588 points and 11 camera scenes. Evidence `cohort-checkpoint-17885096890374683162_755_580_775_580-verified.json`; protocol/models remain open.

### TF-free bounded TFRecord reader verified live

Observed missing-module failure in offline locked CPU Insula, then implemented stdlib CRC32C lookup/checks and bounded streaming envelopes. Four independent bit-at-a-time fixture groups passed without skips: knownvectors/mask, offset/hash/emptyrecords, corrupted/truncated/oversized envelopes, shortreads. Current candidate/test/runtime/live-log/receipt hashes audited; `research/tfrecord-reader-verified.json`. No TensorFlow dependency/import; outercompression/sourcepayload/protobuf/causalinput not yet certified. Ticket19 remains preparing.

### Native causal projection preparation

Live missing-binary failure observed, then native C++ projection compiled against locked pinned protobuf library without runtime mutation. Separate protoc-built/decode-checked fixtures passed four groups: full future truth stays unchanged while model input excludes future states/signals and target/interaction metadata; injected future sensor coverage rejected; invalid timeline/identity rejected; complete current/history sensor counts preserved. Initial checker substring also counted dynamic-map states; corrected field-specific count and retained failed log. Evidence `research/motion-causal-projection-verified.json` (under experiments/waymo-perception). This is analytic native boundary evidence, not source provenance, sensor contents/geometry, acquired ingestion or held-out forecasting. Ticket19 remains open.

### Causal schema preservation gap fixed with live regression

Inspection showed native message copies preserve nested unknown fields. Injected unknown wire fields reproduced acceptance live in priorcandidate; added recursive pinned-schema unknown-field rejection before output and widened current index arithmetic to avoid signed overflow. Five separate native protoc fixture groups passed live after rebuild; evidence `research/motion-causal-projection-schema-verified.json`. Prior projection receipt remains historical and no longer admits changed candidate. Newerrelease unknown fields require explicit schema migration, not silent discard. Actualsource linkage/sensor contents/geometry and scientific evidence remain open.

Independent live checkpoint admission passed for 7912728502266478772_1202_200_1222_200; original source/runtime/current candidates and retained/evicted evidence reconciled. Snapshot now 14/103 point scenes, 474579159 points and 12 camera scenes. Evidence `cohort-checkpoint-7912728502266478772_1202_200_1222_200-verified.json`; protocol/models remain open.

### Actual detector predictions independently checked and natively scored

Seed17 untrained engineering GPU forward/backward produced100 diagnostic decoded proposals, zerooptimizersteps. Failed mount/field-name harness and NumPy-free metrics-root attempt retained separately. Corrected harness used original `nlz` field; separate locked NumPychecker recomputed every prediction count/NLZ over180,827 original measuredpoints, then TF-free native metricroot exported/redecoded100 predictions/45 exact-frame GT boxes and scored successfully. Hash-verified handoff/current producer/runtime/code/source/outputs audited; `research/native-prediction-scoring-verified.json`. Fixtureanchors/NMS/trainmode and oneengineeringframe; no modelquality/heldout claim, ticket07/10scientific closure remains open.

Independent live checkpoint admission passed for 4723255145958809564_741_350_761_350; original source/runtime/current candidates and retained/evicted evidence reconciled. Snapshot now 15/103 point scenes, 509834444 points and 13 camera scenes. Evidence `cohort-checkpoint-4723255145958809564_741_350_761_350-verified.json`; protocol/models remain open.

Independent live checkpoint admission passed for 8454755173123314088_3202_000_3222_000; original source/runtime/current candidates and retained/evicted evidence reconciled. Snapshot now 16/103 point scenes, 541084645 points and 14 camera scenes. Evidence `cohort-checkpoint-8454755173123314088_3202_000_3222_000-verified.json`; protocol/models remain open.

### Observed preprocessing resource inventory

Locked live CPU audit reopened13 externally hash-pinned completed queued checkpoints, checked successful10-stage lifecycles and linked retained point/camera/sidecar publication receipts, and summarized actual stage durations, memory fields and immutable archive sizes. Observed total scene elapsed min447.774s, median615.024s, max690.634s, sum7864.896s. Evidence `experiments/waymo-perception/research/scientific-preprocessing-resource-verified.json` (repository-relative). This is completed-scene preprocessing cost only; manual pilots excluded, remaining87scene processing not extrapolated, no training/evaluation GPU budget or cap freeze. Scientific protocol remains open.

### Training-only anchor distribution preparation

Observed missing statistics module live, then four independent fixture groups passed in locked CPU Insula: hand-computed native medians/counts, validation/development/unknown context refusal, duplicate/badgeometry/nativeclass refusal, empty/permutation invariance. Explicit per-frame-object equal weighting preserves repeated track observations; absent classes remain absent, no guessed anchors. Declaration checks do not establish manifest provenance. Evidence `research/training-box-statistics-verified.json`; actual64training source stats/ROI/anchors/protocol still open. No staging interference or modeltraining.

Independent live checkpoint admission passed for 3894883757914505116_1840_000_1860_000; original source/runtime/current candidates and retained/evicted evidence reconciled. Snapshot now 17/103 point scenes, 574598942 points and 15 camera scenes. Evidence `cohort-checkpoint-3894883757914505116_1840_000_1860_000-verified.json`; protocol/models remain open.

### Independent all-point semantic candidate prepared

Observed missing-module failure live; implemented separate physical XYZ/intensity/elongation localMLP plus globalmax context and native23 output head. Four live CPU Torch fixture groups passed permutationequivariance/singleton/empty/fullpoint support, knownlog23 maskedloss, absent versus undefined targets, invalidfeatures/taxa and finitefullmodelgradients. No detectionforeground selection or sampling. Evidence `research/point-semantic-preparation-verified.json`; candidate architecture not frozen, GPU/nativeinput/resource/optimizer/overfit/export/heldout evidence remain required.

### Real all-point semantic integration independently checked

GPU1 had activecomputePID1094246, so used CPU Torch lockedruntime withoutdevice mounts. One native labeledengineeringframe bothTOPreturns:157,870points,152,773eligible semantic targets, everypoint retained. Nativephysical XYZ/intensity/elongation forward/backwardfinite,0optimizersteps,0.730s modelpath. Separate NumPyInsula checker reopened originalhashpinnedpayloads, reconciled bothreturn pixelorder/uniqueness/native23classoutputs and independently recomputedfull targethistogram. Currentproducer/code/source/output/runtime lineage audited; `research/native-point-semantic-cpu-verified.json`. Engineeringonly; actualGPUcost,scientificfreeze,optimization/export/heldoutmetrics remain open.

### Real semantic predictions reached independent native scoring

Native all157,870 originalpoint predictions across bothTOPreturns separately prepared/checked from trusted model outputs and originalpoint labels. Independent23x23 confusion ignoresonly nativeundefined GT0 and keepsabsentclass IoU1. Separate TF-free metricruntime exportedanddecodedframekeys/bothcompressedvectors exactly, then native22class mIoU agreedwithin1e-6 with independently computed value. Currentproducer/runtime/source/code/artifacts audited; `research/native-point-semantic-scoring-verified.json`. Randomuntrained engineeringmodel only,0optimizersteps,noheldout quality/scientific closure.

Independent live checkpoint admission passed for 13271285919570645382_5320_000_5340_000; original source/runtime/current candidates and retained/evicted evidence reconciled. Snapshot now 18/103 point scenes, 611773330 points and 16 camera scenes. Evidence `cohort-checkpoint-13271285919570645382_5320_000_5340_000-verified.json`; protocol/models remain open.

### Conservative mask-to-point association prepared

Observed missing module failure then four live independent CPUfixturegroups passed nativecamera/u/v pixelorientation/order, explicitvisibility, out-of-bounds/missingcamera abstention, overlappingprompt/crosscamerasemanticconflict abstention and declaredannotation/invalidnamespace refusal. Everypoint retained; masks cannotestablishdepth or visibility. Originstrings do notprovelearnedcheckpoint provenance, which remains required. Evidence `research/mask-point-support-verified.json`; realSAM/camera/visibilityintegration and scientificcomparisons remain open.

Independent live checkpoint admission passed for 8345535260120974350_1980_000_2000_000; original source/runtime/current candidates and retained/evicted evidence reconciled. Snapshot now 19/103 point scenes, 648669999 points and 17 camera scenes. Evidence `cohort-checkpoint-8345535260120974350_1980_000_2000_000-verified.json`; protocol/models remain open.

### Mask normalization contract regression fixed

Live booleanlistmask regression reproduced validation/sampling mismatch (listshapeexception). Normalize validatedmasks once into separateinternalcatalog withoutcaller mutation; five live fixturegroups nowpass. Currentreceipt `research/mask-point-support-normalization-verified.json` supersedesprior changedcandidate evidence. Learnedcamera/SAM provenance, visibility and heldoutresearch remain open.

### Full native point-semantic GPU resource pilot verified

PhysicalGPU1 independently confirmedidle/no computePID before lockedGPU launch. Native157,870points/152,773eligiblelabels fulltwoTOPreturns forward/backwardfinite,0optimizersteps,allocatedpeak813,467,136bytes. Measured0.522s interval includes forward/backward, hostpredictioncopy and outputNPZwrites; not a warm isolatedkernel benchmark. Separate lockedCPUchecker reopens originalhashpinnedpointpayloads, reconcilesallpointpixelidentities/taxonomy/eligiblecounts. Currentcandidate/runtime/driver/producer/artifacts audited; `research/native-point-semantic-gpu-verified.json`. Candidateprotocol/training/heldoutresultsremainopen.

### Camera preprocessing coordinate foundation prepared

Missingmodule livefailure then four independentCPUfixturegroups passed halfpixelcenter mapping versus continuousboxedges, odddimension distinctXYresizefactors, inversegeometry/noimplicitclipping and malformedmetadata refusal. Actualinteger resize/padding required, originalinputs untouched. Evidence `research/camera-coordinates-verified.json`. Interpolator implementation, nativeannotationedge conventions and actual learnedcamera/SAM integration remain open.

Independent live checkpoint admission passed for 1357883579772440606_2365_000_2385_000; original source/runtime/current candidates and retained/evicted evidence reconciled. Snapshot now 20/103 point scenes, 681453360 points and 18 camera scenes. Evidence `cohort-checkpoint-1357883579772440606_2365_000_2385_000-verified.json`; protocol/models remain open.

### Actual Torch resize coordinate parity verified

Two live lockedCPU Torch groups compared actual bilinearalign_cornersFalse/antialiasFalse resizedXYramps against coordinateinverse at odddownsample/upsample dimensions, includingclampedboundarysamples and exactpadding/boxedge distinctions. Tolerance1e-12float64 passes; `research/camera-interpolation-parity-verified.json`. No productionbehavior changed. Actualcamera/SAM preprocessingrecipes/nativeannotation conventions and learnedmodelresults remain open.

Read-only native scientific semantic support pilot passed for 4487677815262010875_4940_000_4960_000: 4699860 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Independent live checkpoint admission passed for 16977844994272847523_2140_000_2160_000; original source/current worker/runtime and retained/evicted evidence reconciled. Accepted 21/103 scenes, 713283823 points, 19 camera lifecycles. Protocol/models remain open.

Recorded original103scene valid-range semantic coverage denominator; current1scene has4,699,860eligible labels, fullcohort and completedlifecycle linkage pending. Updated boundedread-only capture to skip existing successful/failed runs and pin orchestrator SHA; newcapture session41023 confirmedwaitinglive, queue64903alive. No driver/source changes or rawstaging.

### Complete Motion Scenario metadata and bounded source pilot candidate

Authenticated metadata-only inventory exhausted pagination for official v1.2.1 Scenario training/validation shards, checked unique sourcekeys/generations/checksums and persisted allobjectmetadata. Deterministic first-name-per-split objects fitting existingremaining single-source raw cap recorded beforepayload/modeloutcomes in `research/motion-source-pilot.candidate.json`; no rawdownload/staginglease or scientificcohortfreeze. ExtensionIDs require native Scenario parsing and subsequent exactmetadata lookup. Full heldoutforecasting scope remains open.

Independent live checkpoint admission passed for 4487677815262010875_4940_000_4960_000; original source/current worker/runtime and retained/evicted evidence reconciled. Accepted 22/103 scenes, 749268087 points, 20 camera lifecycles. Protocol/models remain open.

Read-only native scientific semantic support pilot passed for 809159138284604331_3355_840_3375_840: 4820976 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- Fresh semantic-support receipt/artifact/source/current-code hash audit admitted scene 809159138284604331_3355_840_3375_840 coverage only: 4,820,976 eligible native labels across 30 annotated frames. Inventory now 2/103 scenes, 9,520,836 eligible labels; prior lifecycle linkage preserved. Queue session 64903 observed live and producer reported this scene lifecycle complete; independent checkpoint admission remains pending. Previous recap turn classified no progress; this turn updates authoritative coverage evidence.

Read-only native scientific semantic support pilot passed for 3966447614090524826_320_000_340_000: 4858414 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- Independently live-Insula audited 809159138284604331_3355_840_3375_840 checkpoint, source receipt hashes, locked root, current verifier, 30 retained lifecycle files and eviction provenance. Processing snapshot now 23/103 scenes, 784781315 points. Previous turn classified progress.

- Fresh semantic receipt/artifact/source/current-code audit admitted 3966447614090524826_320_000_340_000 coverage only: 4858414 eligible labels. Inventory 3/103 scenes, 14379250 eligible labels. Previous goal turn classified progress. Final checkpoint admission remains separate.

- Pinned all64 training-only LiDAR box receipt/payload/generation identities for later distribution replay; total 47802105 source bytes, largest 1800998. This avoids fetching multi-GB seven-component archives solely for anchor statistics. Metadata preparation only; no shared raw lease taken during live queue. Sessions64903 and80012 freshly polled live.

- Independently live-Insula checkpoint verified 3966447614090524826_320_000_340_000, all17 source receipt identities/current code/locked runtime/retained lifecycle and eviction lineage; snapshot 24/103 scenes, 821067958 points. Previous turn classified progress.

Read-only native scientific semantic support pilot passed for 5083516879091912247_3600_000_3620_000: 4694911 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- Previous turn classified progress. Freshly polled live queue64903 and bounded eligibility capture80012; no new lifecycle completion reported. Read-only scientific working-root scan observed 14043088055 bytes, 48965 files; non-atomic while active, not peak/cap-freeze evidence. No restart or competing raw/derived staging.

- Previous turn classified verified wait/storage observation. Fresh audited semantic-support capture for 5083516879091912247_3600_000_3620_000: 4694911 eligible labels. Inventory now4/103 and 19074161 eligible labels; lifecycle still pending. Queue64903 live; capture80012 terminalexit0.

- Previous turn classified progress. Current four-scene support snapshot independently rehashed against original live receipt/artifacts/current consumer and three lifecycle-linkage evidence hashes; all23 histogram totals and eligible denominator agree:19,074,161 labels. Queue64903 and observer86099 freshly polled live. No new checkpoint available; no source restart.

- Previous turn classified progress (full training-box replay plan recorded). Fresh polls confirm queue64903 and capture86099 live; queue has reached sidecar publication for5083516879091912247_3600_000_3620_000. Registry-versus-checkpoint inspection finds no completed unadmitted scene yet. Protocol ticket now directly links full64 replay procedure. No concurrent staging or source restart.

- Previous turn classified verified wait/protocol-link progress. Queue64903 freshly polled live at camera preprocessing; observer86099 still live. Rehashed full64 training-box candidate against original manifest and every source receipt, membership, payload/mirror digest, generation, bytes and row inventory; all match. Metadata audit only; no payload replay or anchor adoption.

- Previous turn classified verified wait/input-identity audit. Fresh independent live Insula checkpoint admission for 5083516879091912247_3600_000_3620_000 passed; processing now25/103 scenes, 856261183 points. Fourth semantic coverage capture reconciled to retained reconstruction/report/source hashes and immutable point publication. Full scientific protocol/comparisons remain open.

- Previous goal turn classified progress (25th live checkpoint admission and fourth support linkage). Fresh polls confirm queue64903 and observer86099 live. Rehashed all currently admitted queued checkpoints against snapshot/registry external pins and recomputed25scene total856,261,183; no new completed checkpoint pending. Protocol prose now uses per-scene linkage inventory instead of stale fixed counts. No competing transfers or restart.

Read-only native scientific semantic support pilot passed for 6142170920525844857_2080_000_2100_000: 4781545 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- Previous goal turn classified verified wait/current-state reconciliation. Capture86099 terminalexit0; fresh receipt/artifacts/current consumer/source/manifest/orchestrator audit admitted 6142170920525844857_2080_000_2100_000 coverage only:4,781,545 labels. Inventory5/103, 23855706 eligible labels. Queue64903 and authoritative PID3958580 verified live; latest scene reconstruction done, lifecycle pending. No restart of active queue.

- Previous turn classified progress (fifth coverage admission). Freshly polled queue64903 and observer94460 live. Added split-separated support snapshot pinned to original manifest/current aggregate: currently observed captures are training-only, so held-out eligibility remains wholly unmeasured by these captures. Overlapping validation memberships explicitly cannot be summed as unique-scene coverage. Scientific freeze remains open.

- Previous turn classified progress (split-separated coverage artifact). This turn verified wait: queue64903 and observer94460 polled live. Latest scene6142170920525844857_2080_000_2100_000 completed point replay/eviction; no unadmitted completed checkpoint found. Split support artifact snapshot SHA and five-scene training-only totals rechecked. No restart or competing staging.

- Previous turn classified verified wait. Sessions64903/94460 freshly polled live. Added native Motion pilot execution plan linked fromticket19, with complete-file admission, generation-pinned HDFS recovery, exact scenario extension identity, acquired-native causal faults and metric handoff. No payload staged or scientific scope reduced.

- Previous turn classified progress (native Motion pilot plan). This turn verified wait: queue64903 and observer94460 freshly polled live; current scene sidecar publication complete, no final checkpoint yet. Rechecked Motion pilot inventory digest, distinct official split object prefixes, generations and each source fitting947,329,295B allowance; metadata only, no acquisition or overlapping lease.

- Previous turn classified verified wait. Current fresh polls confirm sessions64903/94460 live: current scene6142170920525844857_2080_000_2100_000 has completed sidecar eviction and camera preprocessing/publication, with camera replay/eviction still pending. No completed unadmitted checkpoints at inspection. Existing jobs preserved; no new staging or restart. Full research goal remains active.

- Previous turn classified verified wait. Fresh independent live Insula checkpoint for 6142170920525844857_2080_000_2100_000 passed; processing26/103, 891805410 points. Fifth semantic capture linked to retained reconstruction/source/report and point publication. Queue64903 and observer94460 polled live; full scientific study remains open.

- Previous turn classified progress (26th independent checkpoint and fifth semantic lifecycle linkage). Verified wait this turn: sessions64903/94460 freshly polled live, authoritative queuePID3958580 present, no completed unadmitted checkpoints. Live child process observation: [{"pid": 2345259, "command": "python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 17782258508241656695_1354_000_1374_000 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/17782258508241656695_1354_000_1374_000/points --reconstruct "}]. No source restart or competing staging; original103scene cohort and all scientific comparisons retained.

- Previous turn classified verified wait. Fresh sessions64903/94460 polls remain live; queuePID3958580 command verified and active children observed: [{"pid": 2345259, "command": "python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 17782258508241656695_1354_000_1374_000 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/17782258508241656695_1354_000_1374_000/points --reconstruct "}]. No unadmitted complete checkpoint. Same handles retained, no source restart, no extra raw lease; current processing is an external-state wait rather than an impasse.

Read-only native scientific semantic support pilot passed for 17782258508241656695_1354_000_1374_000: 3148482 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- Previous turn classified verified wait. Fresh session64903 and94460 polls confirm live queue/capture, no new producer completion. Current17782258508241656695_1354_000_1374_000 stage log sizes inspected read-only; no source restart or lease collision introduced. Processing26/103 and scientific studies remain open.

- Capture94460 terminalexit0; fresh hashes audited sixth support receipt17782258508241656695_1354_000_1374_000,3,148,482 eligible labels. Snapshot6/103 and27,004,188 labels; final scene lifecycle pending.

- Previous turn classified progress (sixth semantic receipt admission). Fresh queue64903 and observer2837 polls live. Split-separated snapshot refreshed against manifest/native histograms/receipt hashes:6training scenes,27,004,188 labels,5lifecycle links; no development/held-out captures. Original denominators retained.

- Previous turn classified progress (sixth split support snapshot refresh). Current verified wait: sessions64903/2837 freshly polled live and queuePID3958580 argv confirmed. Child stage observation ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/verify-scientific-replay.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/17782258508241656695_1354_000_1374_000/points /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/17782258508241656695_1354_000_1374_000/point-publication /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort"]. No completed unadmitted checkpoint, no restart, no competing data staging. Full103scene and scientific comparison scope retained.

- Previous goal turn classified verified wait. Sessions64903 and2837 freshly polled live this turn; no completed unadmitted checkpoint found. Current scene remains in live lifecycle processing; no active source/queue restarted, no parallel raw staging. Original research goal remains open beyond preprocessing.

- Previous turn classified verified wait. Sessions64903/2837 freshly confirmed live this turn; queuePID3958580 argv confirmed. Active child stage ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/17782258508241656695_1354_000_1374_000/points /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/17782258508241656695_1354_000_1374_000/sidecar-publication --expected-scene-receipt-sha256 547be8e738079b5f0662bf96b0370514435159af3d28e5c4bdd98677ba8a8e5c "]. No completed unadmitted lifecycle checkpoint; original processes retained, no competing staging. No scientific completion claim.

- Previous turn classified verified wait. Freshly polled live sessions64903/2837; no completed unadmitted checkpoint available. Current native scene remains in sidecar/camera lifecycle, capture waits next reconstructed scene. No source restart, parallel lease, cohort shrink or completion claim.

- Previous turn classified verified wait. Fresh queue64903/capture2837 polls live, authoritative queue process confirmed. Current child ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/17782258508241656695_1354_000_1374_000/points /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/17782258508241656695_1354_000_1374_000/sidecar-publication --expected-scene-receipt-sha256 547be8e738079b5f0662bf96b0370514435159af3d28e5c4b"]. No completed unadmitted checkpoint; existing jobs unchanged, no competing source staging. Full research scope remains pending beyond26completed lifecycles.

- Previous turn classified verified wait. Fresh sessions64903/2837 remain live; no completed unadmitted checkpoint found. Waiting on existing lifecycle and capture without source/queue restart or overlapping staging. Full103scene goal and downstream scientific comparisons retained.

- Previous turn classified verified wait. Queue64903 and capture2837 freshly polled live; queuePID3958580 argv and child processes inspected: [{"pid": 2392733, "command": "bwrap --unshare-all --die-with-parent --ro-bind /data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v2 / --ro-bind /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception /experiment --ro-bind /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception /source --bind /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/17782258508241656695_1354_000_1374_000/points /outputs --proc /proc --dev /dev --tmpfs /tmp --clearenv --setenv HOME /tmp/private-home --setenv PATH"}]. No completed unadmitted checkpoint. Existing processes retained; no restart or overlapping raw/derived staging. Goal remains active with scientific studies uncompleted.

- Previous turn classified verified wait with sidecar publication progress observed. Fresh polls confirm sessions64903/2837 live; no completed unadmitted checkpoint. Existing handles retained without source restart or overlapping staging. Full scientific goal remains active.

- Previous turn classified verified wait with native stage progression. Fresh queue64903/capture2837 session polls confirm live; no completed unadmitted checkpoint at inspection. Original processes retained without restart or parallel staging. Scientific training/held-out comparisons remain open.

- Previous turn classified verified wait/camera publication progression. Fresh sessions64903/2837 polls live and queuePID3958580 command verified. No completed unadmitted checkpoint; same running workflow retained. No source restart, cohort shrink or additional staging. Full scientific goal remains open.

- Correction to preceding observation: scene17782258508241656695_1354_000_1374_000 checkpoint completed during the poll and was pending admission. Fresh separate live Insula audit now passed all source/runtime/current verifier/retained worker and eviction provenance checks; processing27/103 and 925687623 points. Sixth semantic support reconciled to retained reconstruction and immutable publication; all6 captures linked.

- Previous turn classified progress (27th live independent checkpoint and sixth semantic lifecycle linkage). Fresh sessions64903/2837 polls remain live, queuePID3958580 argv confirmed. Child stage ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 13830510593707564159_5575_000_5595_000 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/13830510593707564159_5575_000_5595_000/points --reconstruct "]. No unadmitted completed checkpoint. Existing processes retained; full scope remains active without competing staging.

- Previous turn classified verified wait. Fresh sessions64903 and2837 confirmed live; no new completed unadmitted checkpoint at inspection. Same jobs retained; no source restart or parallel staging. Full103scene and scientific research objective remain open.

- Previous turn classified verified wait. Fresh queue64903/capture2837 polls live; queuePID3958580 argv confirmed. Active children ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 13830510593707564159_5575_000_5595_000 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/13830510593707564159_5575_000_5595_000/points --reconstruct "]. No source restart or competing staging; full scientific objective remains open.

Read-only native scientific semantic support pilot passed for 13830510593707564159_5575_000_5595_000: 1933274 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- Previous turn classified verified wait. Freshly polled sessions64903/2837 live; no completed unadmitted lifecycle at inspection. Existing queue/capture retained without restart or competing staging. Full scientific goal remains open.

- Capture2837 terminalexit0; seventh support receipt audited against current code/orchestrator, original source/manifest and output/log/input hashes. Scene13830510593707564159_5575_000_5595_000 contributes1,933,274 eligible labels; inventory7/103 and28,937,462 labels. Split snapshot updated training-only; full lifecycle linkage pending.

- Previous turn classified progress (seventh native support capture admitted). Fresh sessions64903/97895 polls confirm live queue and observer. No completed unadmitted lifecycle at inspection; existing processes retained without source restart/parallel staging. Scientific comparisons remain open beyond27verified lifecycles.

- Previous turn classified verified wait with current point publication progression. Fresh polls confirm sessions64903/97895 live; no completed unadmitted checkpoint. Existing jobs retained without restart or competing staging. Full research goal remains open.

- Previous turn classified verified wait. Sessions64903/97895 freshly polled live and queuePID3958580 argv confirmed. Child stage ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/13830510593707564159_5575_000_5595_000/points /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/13830510593707564159_5575_000_5595_000/sidecar-publication --expected-scene-receipt-sha256 8a41223c916fd251b825c761b37dbf2313d6ea0d8b2e2356f"]. No completed unadmitted checkpoint. Existing jobs retained; no source restart/competing staging. Full scientific objective remains active.

- Previous turn classified verified wait with point replay/eviction progression. Fresh polls confirm sessions64903/97895 live; no completed unadmitted checkpoint. Same jobs retained without source restart or competing raw/derived staging. Full scientific objective remains active beyond preprocessing.

- Previous turn classified verified wait. Fresh sessions64903/97895 polls live and queuePID3958580 argv confirmed; child ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/13830510593707564159_5575_000_5595_000/points /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/13830510593707564159_5575_000_5595_000/sidecar-publication --expected-scene-receipt-sha256 8a41223c916fd251b825c761b37dbf2313d6ea0d8b2e2356f"]. No completed unadmitted checkpoint. Existing jobs retained, no source restart or competing staging. Full scientific goal remains active.

- Previous turn classified verified wait. Fresh queue64903/capture97895 session polls live; no completed unadmitted checkpoint. Original jobs retained without restart or competing staging; full scientific objective remains active.

- Previous turn classified verified wait. Sessions64903/97895 freshly polled live; queuePID3958580 argv confirmed, child ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/13830510593707564159_5575_000_5595_000/points /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/13830510593707564159_5575_000_5595_000/sidecar-publication --expected-scene-receipt-sha256 8a41223c916fd251b825c761b37dbf2313d6ea0d8b2e2356f"]. No completed unadmitted checkpoint; no restart or additional staging. Full scientific research objective remains open.

- Previous turn classified verified wait. Fresh sessions64903/97895 polls confirm live; no completed unadmitted checkpoint at inspection. Existing queue/capture retained without source restart or overlapping staging. Full scientific goal remains active.

- Previous turn classified verified wait. Sessions64903/97895 freshly polled live; queuePID3958580 argv confirmed, child ["bwrap --unshare-all --die-with-parent --ro-bind /data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v2 / --ro-bind /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception /experiment --ro-bind /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception /source --bind /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/13830510593707564159_5575_000_5595_000/points /o"]. No completed unadmitted checkpoint; current processes retained without source restart or overlapping staging. Full scientific objective remains active.

- Previous turn classified verified wait with sidecar publication progression. Fresh sessions64903/97895 polls confirm live; no completed unadmitted checkpoint. Same queue/capture retained without source restart or competing staging. Full scientific objective remains open.

- Previous turn classified verified wait with sidecar eviction/camera preprocessing progression. Fresh sessions64903/97895 polls confirm live; no completed unadmitted checkpoint. Existing jobs retained without source restart or extra staging. Full scientific objective remains active.

- Previous turn classified verified wait. Fresh live independent Insula checkpoint admission for13830510593707564159_5575_000_5595_000 passed current runtime/verifier,17source identities, retained workers/artifacts and eviction provenance. Processing28/103, 950443176 points; seventh semantic capture linked to reconstruction/report/source and immutable point publication. Queue64903/capture97895 freshly polled live. Scientific studies remain open.

- Previous turn classified progress (28th independent live checkpoint admission and seventh support linkage). Fresh queue64903/capture97895 polls live; authoritative queue process argv and child ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 14369250836076988112_7249_040_7269_040 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/14369250836076988112_7249_040_7269_040/points --reconstruct "] inspected. No completed unadmitted checkpoint, no source restart/competing staging. Full scientific comparisons remain open.

- Previous turn classified verified wait with next-scene progression. Fresh sessions64903/97895 polls confirm live; no completed unadmitted checkpoint. Existing workflow retained without restart or competing staging. Full research goal remains active.

- Previous turn classified verified wait. Fresh sessions64903/97895 polls live and authoritative queuePID3958580 argv confirmed; child ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 14369250836076988112_7249_040_7269_040 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/14369250836076988112_7249_040_7269_040/points --reconstruct "]. No completed unadmitted checkpoint, source restart or competing staging. Full scientific objective remains open.

- Previous turn classified verified wait. Fresh session64903/97895 polls confirm live; no completed unadmitted checkpoint. Existing handles preserved without restart or competing staging. Full scientific research objective remains active.

Read-only native scientific semantic support pilot passed for 14369250836076988112_7249_040_7269_040: 5001953 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- Previous turn classified verified wait. Fresh sessions64903/97895 polls confirm live; no completed unadmitted checkpoint. Existing processes retained without restart or competing staging; full scientific goal remains open.

- Capture97895 terminalexit0; eighth native support receipt/artifacts/current consumer/orchestrator/source and manifest hashes independently audited. Scene14369250836076988112_7249_040_7269_040 adds5,001,953 eligible labels; inventory8/103 and33,939,415 labels, all observed training-only. Full scene lifecycle linkage pending.

- Previous turn classified progress (eighth native semantic capture admitted). Fresh queue64903/capture47003 session polls confirm live; no completed unadmitted lifecycle. Existing processes retained without source restart or competing staging. Original scientific goal remains active.

- Previous turn classified verified wait. Fresh sessions64903/47003 polls live; authoritative queuePID3958580 argv confirmed and child ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/verify-scientific-replay.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/14369250836076988112_7249_040_7269_040/points /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/14369250836076988112_7249_040_7269_040/point-publication /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort"]. No completed unadmitted checkpoint; existing jobs retained without restart or competing staging. Full scientific objective remains active.

- Previous turn classified verified wait with point publication progression. Fresh sessions64903/47003 polls confirm live; no completed unadmitted checkpoint. Existing jobs retained without source restart or competing staging. Full scientific research objective remains open.

- Previous turn classified verified wait. Fresh sessions64903/47003 polls confirm live; authoritative queuePID3958580 argv and child ["bwrap --unshare-all --die-with-parent --ro-bind /data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v2 / --ro-bind /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception /experiment --ro-bind /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception /source --bind /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/14369250836076988112_7249_040_7269_040/points /o"] inspected. No completed unadmitted checkpoint, no source restart/competing staging. Full scientific research objective remains open.

- Previous turn classified verified wait. Fresh sessions64903/47003 polls confirm live; no completed unadmitted checkpoint. Existing processes retained without source restart or competing staging. Full scientific goal remains open beyond28verified lifecycles.

- Previous turn classified verified wait with point replay/eviction progression. Fresh sessions64903/47003 polls confirm live; no completed unadmitted checkpoint. Existing jobs retained without restart or competing staging. Full scientific objective remains active.

- Previous turn classified verified wait. Fresh sessions64903/47003 polls live; authoritative queuePID3958580 argv/child ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/14369250836076988112_7249_040_7269_040/points /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/14369250836076988112_7249_040_7269_040/sidecar-publication --expected-scene-receipt-sha256 5867a0b4961e5572269e277140b03edc2b6c99d7683a41e6b"] confirmed. No completed unadmitted checkpoint. Same workflow retained without restart or competing staging; full scientific objective remains open.

- Previous turn classified verified wait. Fresh sessions64903/47003 polls confirm live; no completed unadmitted checkpoint. Existing workflow retained without source restart or competing staging. Full scientific goal remains open.

- Previous turn classified verified wait. Fresh sessions64903/47003 polls live; authoritative queuePID3958580 argv/child [] confirmed. No completed unadmitted checkpoint. Existing jobs retained without source restart or competing staging; full scientific goal remains open.

- Previous turn classified verified wait with sidecar publication progression. Fresh sessions64903/47003 polls confirm live; no completed unadmitted checkpoint. Existing jobs retained without source restart or competing staging; full scientific goal remains active.

- Previous turn classified verified wait with sidecar eviction progression. Fresh sessions64903/47003 polls confirm live; no completed unadmitted checkpoint. Existing workflow retained without source restart or competing staging. Full scientific objective remains open.

- Previous turn classified verified wait with camera preprocessing progression. Fresh sessions64903/47003 polls confirm live; no completed unadmitted checkpoint. Existing handles retained without source restart or competing staging. Full scientific goal remains active.

- Previous turn classified verified wait with camera publication progression. Fresh queue64903/capture47003 polls confirm live; no completed unadmitted checkpoint at inspection. Existing jobs retained without source restart or competing staging. Full scientific objective remains active.

- Correction: checkpoint14369250836076988112_7249_040_7269_040 completed during preceding poll and was pending admission. Fresh separate live Insula audit now passed current runtime/verifier,17source identities and retained/eviction lineage. Processing29/103 and 986930457 points; eighth support capture linked to immutable point publication. Full scientific objective remains open.

- Previous turn classified progress (29th independent checkpoint and eighth support lifecycle linkage). Fresh sessions64903/47003 polls live; authoritative queuePID3958580 argv/child ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 11004685739714500220_2300_000_2320_000 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/11004685739714500220_2300_000_2320_000/points --reconstruct "] inspected. No completed unadmitted checkpoint. Existing jobs retained without source restart/competing staging. Full scientific objective remains active.

- Previous turn classified verified wait with next-scene progression. Fresh sessions64903/47003 polls confirm live; no completed unadmitted checkpoint. Existing processes retained without source restart or competing staging. Full scientific research objective remains open.

- Previous turn classified verified wait. Fresh sessions64903/47003 polls live; queuePID3958580 argv/child ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 11004685739714500220_2300_000_2320_000 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/11004685739714500220_2300_000_2320_000/points --reconstruct "] confirmed. No completed unadmitted checkpoint. Existing processes retained without restart or competing staging. Full scientific objective remains open.

Read-only native scientific semantic support pilot passed for 11004685739714500220_2300_000_2320_000: 3085175 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- Previous turn classified verified wait. Fresh queue64903/capture47003 polls confirm live; no completed unadmitted checkpoint or completed current reconstruction receipt at inspection. Existing jobs retained without restart/competing staging. Scientific goal remains active.

- Correction: current reconstruction receipt was present at inspection; re-poll confirms point preprocessing success and capture47003 terminalexit0. Ninth support receipt fully hash audited:3,085,175 eligible labels; snapshot9/103 and37,024,590 labels. Full lifecycle linkage pending.

- Previous turn classified progress (ninth support receipt admission). Fresh sessions64903/9596 polls confirm live; no completed unadmitted checkpoint. Existing processes retained without source restart or competing staging. Full scientific objective remains active beyond29verified lifecycles.

- Previous turn classified verified wait with point publication progression. Fresh sessions64903/9596 polls confirm live; no completed unadmitted checkpoint. Existing handles retained without restart or competing staging; full scientific objective remains active.

- Previous turn classified verified wait. Fresh sessions64903/9596 polls live; authoritative queuePID3958580 argv and child ["python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/11004685739714500220_2300_000_2320_000/points /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/11004685739714500220_2300_000_2320_000/sidecar-publication --expected-scene-receipt-sha256 9ee7cbf1d58f452b2b44c0e4abca9119201a0a448029ab278"] confirmed. No completed unadmitted checkpoint. Existing processes retained without restart or competing staging; full scientific objective remains open.

Read-only native scientific semantic support pilot passed for 15539619898625779290_760_000_780_000: 4360464 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T20:57:59.059064+00:00: Independent live Insula checkpoint audit admitted 11004685739714500220_2300_000_2320_000; 24,384,748 points, all retained lifecycle evidence reconciled. Processing 30/103, 1,011,315,205 points. Driver PID 3958580 and sessions 64903/9596 were confirmed live this turn; previous recap was a status-only turn. Scientific comparisons remain open.

- 2026-09-30T20:59:13.870419+00:00: Admitted native semantic support for 15539619898625779290_760_000_780_000 (4,360,464 eligible points), rehashed live receipt/artifacts/current consumer and orchestrator. Linked 11004685739714500220_2300_000_2320_000 to independently checked checkpoint and point-publication report. Coverage 10/103, 41,385,054 eligible point elements; nine lifecycle linked. Session 64903 confirmed live, session 9596 completed exit zero. Coverage only; scientific gates open.

- 2026-09-30T21:00:13.413398+00:00: Verified wait: driver PID 3958580 confirmed live and session 64903 advanced point publication for 15539619898625779290_760_000_780_000; semantic capture session 48379 confirmed live waiting. No complete unadmitted checkpoint at inspection. Non-atomic derived working-root observation 7,588,480,991 bytes/30,104 files versus proposed 15 GiB cap; cap and scientific training protocol remain unfrozen. Previous turn made evidence admission/linkage progress.

- 2026-09-30T21:00:59.353135+00:00: Verified wait: live session 64903 returned successful point replay and point eviction for 15539619898625779290_760_000_780_000; session 48379 remained live awaiting next reconstruction. Original driver PID 3958580 remains live. Current point publication report hash reconciles with pre-eviction semantic capture; full-scene lifecycle admission still pending, so no completed-scene or lifecycle-linked count increment.

- 2026-09-30T21:02:14.938314+00:00: Verified wait: original driver 3958580 and semantic session 48379 confirmed live. Sidecar transfer PID 2821192 observed during HDFS put then disappeared before secondary I/O inspection; this is child turnover, not driver termination. Current direct children: 2816302. No promotion or restart.

- 2026-09-30T21:03:04.092184+00:00: Verified wait: session 64903 advanced sidecar publication with exit zero for 15539619898625779290_760_000_780_000; original driver /proc/3958580/cmdline confirmed current pipeline, child live bwrap 2837802. Capture session 48379 remains live waiting. Full scene checkpoint absent; no coverage/lifecycle promotion.

- 2026-09-30T21:03:58.452729+00:00: Verified wait: live queue session 64903 advanced camera preprocessing exit zero for 15539619898625779290_760_000_780_000; /proc identified publisher PID 2844718. Host rehash matched all three camera-evidence worker receipts and successful checks. Full live lifecycle audit/publication/replay not yet admitted, so totals unchanged. Semantic capture 48379 remains live.

- 2026-09-30T21:05:06.747114+00:00: Live independent Insula checkpoint audit admitted 15539619898625779290_760_000_780_000; 33,627,112 points. All17 source hashes/current manifest/current verifier reconciled before and after. Processing 31/103, 1,044,942,317 points; scientific comparisons open. Sessions 64903/48379 remain live.

- 2026-09-30T21:05:58.390580+00:00: Reconciled semantic capture 15539619898625779290_760_000_780_000 with admitted live checkpoint, native worker receipt and immutable point publication/report. All10 captured scenes lifecycle linked, 41,385,054 eligible point elements; cohort eligibility incomplete, no scientific closure.

- 2026-09-30T21:06:47.230615+00:00: Verified wait: sessions 64903/48379 and original driver 3958580 live. Authoritative child 2851621 reconstructs 14004546003548947884_2331_861_2351_861. No unadmitted checkpoint. Rechecked all10 semantic linkage/support receipt pins and aggregate/split snapshot identity: 41,385,054 eligible labels. No scientific closure.

- 2026-09-30T21:07:19.475477+00:00: Verified wait: original driver PID3958580 confirmed live with direct children ['2851621']; sessions64903/48379 polled current handles. Scene14004546003548947884_2331_861_2351_861 reconstruction/checkpoint inspected; no inferred completion or restart. Previous turn verified waiting and existing lineage.

Read-only native scientific semantic support pilot passed for 14004546003548947884_2331_861_2351_861: 6958235 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T21:08:12.631830+00:00: Capture session48379 completed exitzero; independently reconciled live support receipt/artifacts/current identities for 14004546003548947884_2331_861_2351_861, 6,958,235 eligible point elements. Coverage11/103, 48,343,289 eligible elements, ten lifecycle linked; newest linkage pending. Driver64903 advanced point preprocessing exitzero.

- 2026-09-30T21:09:35.044147+00:00: Verified wait: sessions64903/38554 live on current polls; /proc confirmed original processing driver and point publisher2918226 for 14004546003548947884_2331_861_2351_861. Re-polled same queue after bounded30-second observation; driver current children 2945477. No checkpoint promoted or process restarted.

- 2026-09-30T21:10:53.053976+00:00: Verified wait: current queue64903 and capture38554 live; authoritative child2945477 runs native point replay for14004546003548947884_2331_861_2351_861. Host check reconciled newest semantic report/reconstruction identities with immutable point publication. Re-polled same queue after30seconds; live driver direct children 2979878. Full checkpoint absent at initial inspection; no final lifecycle promotion.

- 2026-09-30T21:12:10.692536+00:00: Verified wait: current sessions64903/38554 live; original driver3958580 and publisher2979878 confirmed under /proc, sidecar transfer child2992897 observed. Scene14004546003548947884_2331_861_2351_861 checkpoint not complete at initial inspection. Same queue polled after30seconds; current children 2979878. Full cohort and scientific comparisons remain open.

- 2026-09-30T21:13:28.811344+00:00: Verified wait: queue64903 advanced sidecar-publication exitzero for14004546003548947884_2331_861_2351_861; capture38554 live. Original driver3958580 confirmed and same handle repolled after30seconds; current children [('3030898', 'python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/verify-camera-replay.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/14004546003548947884_2331_861_2351_861/camera /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/14004546003548947884_2331_861_2351_861/camera-publication /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1')]. No completed checkpoint at initial inspection or coverage promotion.

- 2026-09-30T21:14:39.904818+00:00: Independently admitted live Insula checkpoint 14004546003548947884_2331_861_2351_861; 38,653,298 points. All17 source/current manifest/verifier pins checked before and after. Processing 32/103, 1,083,595,615 points. Scientific comparisons remain open.

- 2026-09-30T21:15:32.714768+00:00: Reconciled semantic support 14004546003548947884_2331_861_2351_861 with independently admitted live checkpoint and immutable point publication/reconstruction report. All11 semantic captures lifecycle linked;48,343,289 eligible elements. Scientific comparisons remain open.

- 2026-09-30T21:16:57.912892+00:00: Verified wait: original driver3958580 confirmed current queue, live child3033260 reconstructing1005081002024129653_5313_150_5333_150. Sessions64903/38554 polled and same handles repolled after30seconds; current driver children 3033260. No unadmitted completed checkpoint at initial inspection. No reduced cohort or scientific completion claim.

Read-only native scientific semantic support pilot passed for 1005081002024129653_5313_150_5333_150: 4654641 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T21:17:28.907204+00:00: Verified wait: sessions64903/38554 polled current handles; original driver3958580 confirmed live with children 3059514. Non-atomic active derived storage observed 14,034,705,152 bytes/14,385 files vs proposed15GiB; no peak/cap freeze or scientific closure.

- 2026-09-30T21:17:59.071645+00:00: Capture38554 completed exitzero; live support receipt/artifacts/current consumer/orchestrator/source/manifest rehashed for1005081002024129653_5313_150_5333_150,4,654,641 eligible points. Admitted coverage12/103,52,997,930 eligible labels, eleven lifecycle linked; newest linkage pending. Scientific comparisons open.

- 2026-09-30T21:19:17.582342+00:00: Verified wait: sessions64903/40189 remain live; original driver3958580 command confirmed with point publisher3059514 for1005081002024129653_5313_150_5333_150. No complete unadmitted checkpoints at initial inspection. Same queue re-polled after30seconds; current direct children 3093258. Scientific comparisons remain open.

- 2026-09-30T21:20:41.127372+00:00: Verified wait: current queue64903 advanced point replay and point eviction exitzero for1005081002024129653_5313_150_5333_150. Semantic40189 live waiting. Support report/reconstruction pins reconciled with point publication. Authoritative child3116106 observed sidecar publication; same queue polled after30seconds and driver3958580 current children 3116106. No final checkpoint promotion.

- 2026-09-30T21:21:58.823078+00:00: Verified wait: original driver3958580 confirmed live; sidecar publisher3116106 with transfer child3158099 observed for1005081002024129653_5313_150_5333_150. Sessions64903/40189 live, same queue repolled after30seconds; current children . No unadmitted completed checkpoint at initial inspection, no restart or snapshot promotion.

- 2026-09-30T21:23:19.020458+00:00: Verified wait: sessions64903/40189 confirmed live; original driver3958580 child3188426 runs scientific-camera-preprocess for1005081002024129653_5313_150_5333_150. No complete checkpoint initially available. Same queue repolled after30seconds; current children 3195652. No scene promotion or restart; scientific scope unchanged.

- 2026-09-30T21:24:22.447427+00:00: Independent live Insula checkpoint admitted 1005081002024129653_5313_150_5333_150; 34,357,856 points. All17 source/current manifest/verifier pins rechecked before/after. Processing33/103,1,117,953,471 points; scientific comparisons remain open.

- 2026-09-30T21:25:20.306587+00:00: Reconciled semantic capture1005081002024129653_5313_150_5333_150 with independently admitted live checkpoint and immutable point publication/reconstruction report. All12 semantic captures lifecycle linked,52,997,930 eligible elements. Current queue64903/capture40189 polled live; scientific comparisons remain open.

- 2026-09-30T21:26:41.859794+00:00: Verified wait: original processing driver3958580 live with native reconstruction child3200138 for13506499849906169066_120_000_140_000. Sessions64903/40189 repolled current handles after30seconds; current direct children 3200138. No completed unadmitted checkpoint initially available. Scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 13506499849906169066_120_000_140_000: 4282138 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T21:27:32.017618+00:00: Capture40189 completed exitzero; current live receipt/artifact/source/manifest/consumer/orchestrator identities verified for13506499849906169066_120_000_140_000,4,282,138 eligible point elements. Coverage13/103,57,280,068 eligible labels; twelve lifecycle linked, newest pending. Driver64903 advanced preprocessing exitzero and /proc confirms original driver alive; scientific scope unchanged.

- 2026-09-30T21:28:48.557260+00:00: Verified wait: queue64903/capture11570 confirmed live; original driver3958580 points publisher3250849 observed for13506499849906169066_120_000_140_000. No complete unadmitted checkpoint initially available. Same queue repolled after30seconds; current direct children 3279887. Scientific comparison gates open, no scope reduction.

- 2026-09-30T21:30:07.405407+00:00: Verified wait: original driver3958580 /proc command confirmed; live queue64903 and capture11570 polled. Semantic report/reconstruction identities for13506499849906169066_120_000_140_000 matched immutable point publication. Same queue repolled after30seconds; current children 3286208. No final checkpoint initially available and no coverage promotion.

- 2026-09-30T21:31:22.939016+00:00: Verified wait: original driver3958580 confirmed live with sidecar publisher3286208/child3289577 for13506499849906169066_120_000_140_000; queue64903 and semantic11570 live on polls. Same queue repolled after30seconds, current direct children 3286208. No completed unadmitted checkpoint initially available. Scientific comparisons open, no process restart or narrowed scope.

- 2026-09-30T21:32:38.045425+00:00: Verified wait: queue64903 advanced sidecar publication exitzero for13506499849906169066_120_000_140_000, semantic11570 remains live. Original driver3958580 command and child3301029 observed. Same queue polled after30seconds; current children . No complete unadmitted checkpoint at initial inspection; scientific comparisons remain open.

- 2026-09-30T21:34:08.949171+00:00: Verified wait: queue64903 advanced camera publication and camera replay exitzero for13506499849906169066_120_000_140_000; original driver3958580 live, current children 3317356; capture11570 live on initial poll. Full checkpoint absent on latest directory inspection. No final scene promotion.

- 2026-09-30T21:34:52.167575+00:00: Independent live Insula checkpoint admitted13506499849906169066_120_000_140_000; all17 source/current manifest/verifier pins rechecked before/after. Processing34/103,1,150,111,774 points. Scientific comparisons remain open.

- 2026-09-30T21:35:41.403076+00:00: Reconciled semantic capture13506499849906169066_120_000_140_000 with independently admitted live checkpoint and immutable point publication/reconstruction report. All13 semantic captures lifecycle linked,57,280,068 eligible elements. Queue64903/capture11570 live on current polls; scientific comparisons remain open.

- 2026-09-30T21:37:01.724970+00:00: Verified wait: original driver3958580 confirmed live, reconstruction child3317356 for6559997992780479765_1039_000_1059_000. Queue64903/capture11570 repolled current handles after30seconds; direct children 3317356. No complete unadmitted checkpoint initially available. Scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 6559997992780479765_1039_000_1059_000: 4428512 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T21:37:51.378371+00:00: Capture11570 completed exitzero; live receipt/artifact/source/manifest/current consumer/orchestrator rehashed for6559997992780479765_1039_000_1059_000,4,428,512 eligible point elements. Coverage14/103,61,708,580 eligible labels; thirteen lifecycle linked, newest pending. Original driver3958580 live, point publisher3341371 observed. Scientific comparisons open.

- 2026-09-30T21:39:08.073993+00:00: Verified wait: current queue64903/capture10021 live; original driver3958580 command confirmed and point publisher3341371 observed for6559997992780479765_1039_000_1059_000. No complete unadmitted checkpoint at initial inspection. Same queue repolled after30seconds; current children 3351985. No training or scientific closure.

- 2026-09-30T21:40:28.789124+00:00: Verified wait: queue64903 advanced point replay and point eviction exitzero for6559997992780479765_1039_000_1059_000; capture10021 remains live waiting. Current semantic report/reconstruction matched point publication. Original driver3958580 live, sidecar publisher3358882 observed. Same queue polled after30seconds; direct children 3358882. No complete unadmitted checkpoint initially available; scientific comparisons open.

- 2026-09-30T21:41:46.001013+00:00: Verified wait: original driver3958580 live with sidecar publisher3358882/child3361877 for6559997992780479765_1039_000_1059_000. Current queue64903/capture10021 confirmed live and same queue repolled after30seconds; direct children 3358882. No completed unadmitted checkpoint initially available; scientific comparisons open.

- 2026-09-30T21:43:05.270957+00:00: Verified wait: live queue64903 advanced sidecar publication exitzero for6559997992780479765_1039_000_1059_000; capture10021 live. Original driver3958580 /proc command confirmed, child3377192 observed. Same queue repolled after30seconds; current direct children 3385548. No completed unadmitted checkpoint at initial inspection; scientific comparisons open.

- 2026-09-30T21:44:05.913535+00:00: Independently admitted live Insula checkpoint6559997992780479765_1039_000_1059_000; all17 source/current manifest/verifier pins rechecked before/after. Processing35/103,1,183,612,151 points. Scientific comparisons remain open.

- 2026-09-30T21:44:59.307708+00:00: Reconciled semantic capture6559997992780479765_1039_000_1059_000 with independently admitted live checkpoint and immutable point publication/reconstruction report. All14 semantic captures lifecycle linked,61,708,580 eligible elements. Queue64903/capture10021 live on current polls; scientific comparisons remain open.

- 2026-09-30T21:46:26.611664+00:00: Verified wait: original driver3958580 live with reconstruction child3388604 for3224923476345749285_4480_000_4500_000. Queue64903/capture10021 repolled current handles after30seconds; current direct children 3388604. No complete unadmitted checkpoint initially available; scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 3224923476345749285_4480_000_4500_000: 5103365 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T21:47:17.060185+00:00: Capture10021 completed exitzero; current live receipt/artifact/source/manifest/consumer/orchestrator identities rehashed for3224923476345749285_4480_000_4500_000,5,103,365 eligible elements. Coverage15/103,66,811,945 eligible labels; fourteen lifecycle linked, newest pending. Queue64903 preprocessing exitzero, original driver3958580 alive; scientific scope unchanged.

- 2026-09-30T21:48:36.430425+00:00: Verified wait: current queue64903/capture95601 confirmed live; original driver3958580 point publisher3429413 observed for3224923476345749285_4480_000_4500_000. No complete unadmitted checkpoint initially available. Same queue repolled after30seconds; current direct children 3452027. Scientific comparison gates open.

- 2026-09-30T21:49:57.564737+00:00: Verified wait: queue64903/capture95601 live; original driver3958580 and replay worker3452027 observed for3224923476345749285_4480_000_4500_000. Support report/reconstruction pins matched immutable point publication. Same queue repolled after30seconds; current children 3461859. No completed unadmitted checkpoint initially available; scientific scope unchanged.

- 2026-09-30T21:51:16.688054+00:00: Verified wait: original driver3958580 live with sidecar publisher3461859/child3464351 for3224923476345749285_4480_000_4500_000; current queue64903/capture95601 confirmed live. Same queue repolled after30seconds; direct children 3461859. No complete unadmitted checkpoint initially available; no restart, scientific comparisons open.

- 2026-09-30T21:52:36.638699+00:00: Verified wait: original driver3958580 live with sidecar publisher3461859 for3224923476345749285_4480_000_4500_000; queue64903/capture95601 confirmed current live handles. Same queue repolled after30seconds; children 3484527. No completed unadmitted checkpoint initially available. Scientific comparisons remain open.

- 2026-09-30T21:54:00.511382+00:00: Verified wait: queue64903 advanced camera preprocessing/publication for3224923476345749285_4480_000_4500_000; capture95601 live. Original driver3958580 confirmed, replay3493366 observed; same queue repolled after30seconds, current children 3497612. Complete unadmitted checkpoints now ['3224923476345749285_4480_000_4500_000']; scientific comparisons open.

- 2026-09-30T21:54:39.929935+00:00: Independently admitted live Insula checkpoint3224923476345749285_4480_000_4500_000; all17 source/current manifest/verifier pins rechecked before/after. Processing36/103,1,221,021,470 points. Scientific comparisons remain open.

- 2026-09-30T21:55:35.477725+00:00: Reconciled semantic capture3224923476345749285_4480_000_4500_000 with independently admitted live checkpoint and immutable point publication/reconstruction report. All15 semantic captures lifecycle linked,66,811,945 eligible elements. Queue64903/capture95601 live on current polls; scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 14250544550818363063_880_000_900_000: 4843949 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T21:56:53.885753+00:00: Verified wait: original driver3958580 live with reconstruction3497612 for14250544550818363063_880_000_900_000. Queue64903/capture95601 repolled same current handles after30seconds; direct children . No complete unadmitted checkpoint initially available. Scientific comparisons remain open.

- 2026-09-30T21:57:24.150670+00:00: Capture95601 completed exitzero; live receipt/artifact/source/manifest/current consumer/orchestrator rehashed for14250544550818363063_880_000_900_000,4,843,949 eligible elements. Coverage16/103,71,655,894 eligible labels; fifteen lifecycle linked, newest pending. Scientific comparisons open.

- 2026-09-30T21:58:42.074990+00:00: Verified wait: original driver3958580 confirmed live, point publisher3521411 observed for14250544550818363063_880_000_900_000. Current queue64903/capture1368 live on polls; same queue repolled after30seconds; current children 3533004. No completed unadmitted checkpoint initially available. Scientific comparisons remain open.

- 2026-09-30T22:00:01.482731+00:00: Verified wait: queue64903/capture1368 live; original driver3958580 confirmed. Semantic report/reconstruction for14250544550818363063_880_000_900_000 reconciled with immutable point publication. Same queue repolled after30seconds; direct children 3551317. No complete unadmitted checkpoint initially available; scientific comparisons open.

- 2026-09-30T22:01:23.502934+00:00: Verified wait: original driver3958580 live with sidecar publisher3551317/child3553119 for14250544550818363063_880_000_900_000. Current queue64903/capture1368 confirmed live; same queue repolled after30seconds; direct children 3551317. No complete unadmitted checkpoint initially available; scientific scope unchanged.

- 2026-09-30T22:02:43.626888+00:00: Verified wait: queue64903 advanced sidecar publication exitzero for14250544550818363063_880_000_900_000; capture1368 remains live. Original driver3958580 command confirmed, child3570345 observed. Same queue repolled after30seconds; direct children 3577636. No complete unadmitted checkpoint initially available; scientific comparisons open.

- 2026-09-30T22:04:34.958692+00:00: Independently admitted live Insula checkpoint14250544550818363063_880_000_900_000; all17 source/current manifest/verifier pins rechecked before/after. Processing37/103,1,256,971,612 points. Scientific comparisons remain open.

- 2026-09-30T22:05:28.300570+00:00: Reconciled semantic capture14250544550818363063_880_000_900_000 with independently admitted live checkpoint and immutable point publication/reconstruction report. All16 semantic captures lifecycle linked,71,655,894 eligible elements. Queue64903/capture1368 live on current polls; scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 2088865281951278665_4460_000_4480_000: 4317715 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T22:06:51.819138+00:00: Verified wait: original driver3958580 live with reconstruction3589235 for2088865281951278665_4460_000_4480_000. Current queue64903/capture1368 repolled same handles after30seconds; direct children . No complete unadmitted checkpoint initially available. Scientific comparisons remain open.

- 2026-09-30T22:07:21.390590+00:00: Capture1368 completed exitzero; current live receipt/artifact/source/manifest/consumer/orchestrator pins rehashed for2088865281951278665_4460_000_4480_000,4,317,715 eligible elements. Coverage17/103,75,973,609 eligible labels; sixteen lifecycle linked,newest pending. Scientific comparisons open.

- 2026-09-30T22:08:50.348346+00:00: Verified wait: original driver3958580 confirmed live, point publisher3620454 observed for2088865281951278665_4460_000_4480_000. Queue64903/capture13965 live on current polls; same queue repolled after30seconds; direct children 3631288. No complete unadmitted checkpoint initially available; scientific comparisons open.

- 2026-09-30T22:10:12.330858+00:00: Verified wait: queue64903 advanced point replay/eviction exitzero for2088865281951278665_4460_000_4480_000; capture13965 live. Support report/reconstruction matched immutable point publication. Original driver3958580 live, sidecar publisher3641447 observed; same queue repolled after30seconds, direct children 3641447. No complete unadmitted checkpoint initially available; scientific comparisons open.

- 2026-09-30T22:11:30.508021+00:00: Verified wait: original driver3958580 live with sidecar publisher3641447/child3644588 for2088865281951278665_4460_000_4480_000. Current queue64903/capture13965 confirmed live; same queue repolled after30seconds; direct children 3641447. No complete unadmitted checkpoint initially available; scientific comparisons open.

- 2026-09-30T22:12:47.171040+00:00: Verified wait: current queue64903/capture13965 confirmed live; original driver3958580 and sidecar publisher3641447 observed for2088865281951278665_4460_000_4480_000. Same queue repolled after30seconds; current children 3670840. No complete unadmitted checkpoint initially available; no restart or scientific closure.

- 2026-09-30T22:14:07.831029+00:00: Verified wait: queue64903 advanced camera preprocessing/publication for2088865281951278665_4460_000_4480_000, capture13965 live. Original driver3958580/replay3679599 observed. Same queue repolled after30seconds; children 3696679; complete unadmitted checkpoints ['2088865281951278665_4460_000_4480_000']. Scientific comparisons open.

- 2026-09-30T22:14:47.963087+00:00: Independently admitted live Insula checkpoint2088865281951278665_4460_000_4480_000; all17 source/current manifest/verifier pins rechecked before/after. Processing38/103,1,288,624,345 points. Scientific comparisons remain open.

- 2026-09-30T22:15:43.289436+00:00: Reconciled semantic capture2088865281951278665_4460_000_4480_000 with independently admitted live checkpoint and immutable point publication/reconstruction report. All17 semantic captures lifecycle linked,75,973,609 eligible elements. Queue64903/capture13965 live on current polls; scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 12856053589272984699_1020_000_1040_000: 4943504 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T22:17:04.154609+00:00: Verified wait: original driver3958580 live with reconstruction3696679 for12856053589272984699_1020_000_1040_000. Current queue64903/capture13965 repolled same handles after30seconds; direct children . No complete unadmitted checkpoint initially available; scientific comparisons remain open.

- 2026-09-30T22:17:35.365763+00:00: Capture13965 completed exitzero; current live receipt/artifact/source/manifest/consumer/orchestrator pins rehashed for12856053589272984699_1020_000_1040_000,4,943,504 eligible elements. Coverage18/103,80,917,113 eligible labels; seventeen lifecycle linked,newest pending. Scientific comparisons open.

- 2026-09-30T22:18:56.500332+00:00: Verified wait: original driver3958580 live, point publisher3743741 observed for12856053589272984699_1020_000_1040_000. Queue64903/capture59293 confirmed live; same queue repolled after30seconds; direct children 3760843. No complete unadmitted checkpoint initially available; scientific comparisons open.

- 2026-09-30T22:20:17.522552+00:00: Verified wait: queue64903/capture59293 live; original driver3958580 and replay3760843 observed for12856053589272984699_1020_000_1040_000. Support report/reconstruction matched immutable point publication. Same queue repolled after30seconds; direct children 3787851. No complete unadmitted checkpoint initially available; scientific comparisons open.

- 2026-09-30T22:21:36.631150+00:00: Verified wait: original driver3958580 live, sidecar publisher3787851/child3792166 observed for12856053589272984699_1020_000_1040_000. Current queue64903/capture59293 confirmed live; same queue repolled after30seconds; direct children 3787851. No complete unadmitted checkpoint initially available; scientific comparisons open.

- 2026-09-30T22:22:54.273115+00:00: Verified wait: current queue64903/capture59293 confirmed live; original driver3958580 and sidecar publisher3787851 observed for12856053589272984699_1020_000_1040_000. Same queue repolled after30seconds; direct children 3819532. No complete unadmitted checkpoint initially available; scientific comparisons open.

Read-only native scientific semantic support pilot passed for 11489533038039664633_4820_000_4840_000: 5150052 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T22:29:28.448431+00:00: independently live Insula audited scene 12856053589272984699_1020_000_1040_000: 36,765,151 points; publication/replay/three evictions reconciled. Processing snapshot 39/103 scenes, 1,325,389,496 points. Evidence: `cohort-checkpoint-12856053589272984699_1020_000_1040_000-verified.json`. Semantic lifecycle linkage remains pending; scientific protocol and models remain open.

- 2026-09-30T22:30:59.906963+00:00: semantic capture session 59293 terminal exit 0; scene 11489533038039664633_4820_000_4840_000 independently counted 5,150,052 eligible labels and hash-audited for admission. Scene 12856053589272984699_1020_000_1040_000 support host-linked to its independently live-audited checkpoint/publication. Coverage now 19/103, 86,067,165 eligible labels, 18 lifecycle-linked; split snapshot refreshed. Host linkage adds provenance, not a new live computation; studies remain open.

- 2026-09-30T22:32:33.697150+00:00: verified wait: session 64903 remains live, point publication for 11489533038039664633_4820_000_4840_000 returned 0; authoritative driver PID 3958580 and child inspected. Semantic capture session 97734 also polled live, awaiting next completed reconstruction. Working-tree observation 14,892,994,488 bytes across 22,539 files; non-atomic, not peak or cap certification. No new lifecycle checkpoint admitted.

- 2026-09-30T22:33:51.584525+00:00: verified wait, existing session 64903 polled live twice and driver PID 3958580 confirmed with child 3965860: `python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/11489533038039664633_4820_000_4840_000/points /data02/home/philip.yang/.cach`. Capture session 97734 polled live awaiting completed reconstruction. No unadmitted full checkpoint at initial inspection; no restart or completion claim.

- 2026-09-30T22:35:09.501959+00:00: verified wait, existing session 64903 sidecar-publication exit 0 for 11489533038039664633_4820_000_4840_000. Live process tree showed CPU-running Insula sidecar eviction; subsequent driver child 4005259 confirmed live (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/verify-camera-replay.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/114`). Semantic session 97734 also polled live. No restart; full lifecycle admission still pending.

- 2026-09-30T22:36:17.127357+00:00: independent live Insula checkpoint audit admitted 11489533038039664633_4820_000_4840_000; 38,472,032 points, all publication/replay/eviction lineage reconciled. Snapshot 40/103, 1,363,861,528 points. Evidence `cohort-checkpoint-11489533038039664633_4820_000_4840_000-verified.json`; scientific studies remain open.

- 2026-09-30T22:37:10.980459+00:00: scene 11489533038039664633_4820_000_4840_000 semantic support host-linked to independently live-audited checkpoint, retained reconstruction receipt and published report hash; all 19 admitted semantic captures now lifecycle-linked. Refreshed split snapshot hash. Coverage-only provenance reconciliation, not a new live model experiment.

- 2026-09-30T22:38:31.827574+00:00: verified wait: sessions 64903 and 97734 polled live twice; original queue advanced to scene 13619063687271391084_1519_680_1539_680 reconstruction. Authoritative driver PID 3958580 child 4010609 confirmed (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 13619063687271391084_1519_680_1539_680 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientif`). No new complete lifecycle checkpoint at initial inspection, no restart, scientific scope unchanged.

Read-only native scientific semantic support pilot passed for 13619063687271391084_1519_680_1539_680: 4748573 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T22:40:37.231889+00:00: semantic session 97734 terminal exit 0; scene 13619063687271391084_1519_680_1539_680 admitted after receipt/artifact/source/manifest/current-code checks: 4,748,573 eligible labels. Coverage 20/103, 90,815,738 labels; lifecycle linkage pending. Initial host audit used incorrect receipt path and made no writes; corrected to retained evidence/reconstruction/receipt.json. Next capture session 12631 live awaiting reconstruction.

- 2026-09-30T22:41:58.771092+00:00: verified wait: existing queue session 64903 live after successful point publication for 13619063687271391084_1519_680_1539_680; independent native point replay child observed. Subsequent authoritative driver child 4081987 confirmed live (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/1361906368727139`). Capture session 12631 polled live, waiting. No full lifecycle checkpoint ready at initial inspection; no restart or scientific completion claim.

- 2026-09-30T22:43:20.246825+00:00: verified wait: queue session 64903 polled live twice; process tree confirmed scene 13619063687271391084_1519_680_1539_680 sidecar publication through Waystone/native HDFS put. Driver child 4081987 still live (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort`). Capture session 12631 polled live awaiting next reconstruction. No new full checkpoint at initial inspection; preserved original jobs and cohort.

- 2026-09-30T22:44:40.572023+00:00: verified wait: original session 64903 polled live twice; authoritative PID 3958580 process tree confirmed 1 live descendants, current child `python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-camera-preprocess.py --scene 13619063687271391084_1519_680_1539_680 --output /data02/home/philip.yang/.cache/waystone/waymo-pe`. Session 12631 polled live awaiting reconstruction. No unadmitted full checkpoint at initial inspection. Existing HDFS publication preserved; observation is not terminal evidence.

- 2026-09-30T22:45:58.788402+00:00: verified wait, queue session 64903 camera preprocessing/publication exit 0 for 13619063687271391084_1519_680_1539_680; independent camera replay running. Authoritative driver child 4136578 confirmed (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 15628918650068847391_8077_670_8097_670 --output /data02/home/philip.yang/.cache/waystone/waymo-perceptio`); capture session 12631 polled live. Unadmitted checkpoints observed: ['13619063687271391084_1519_680_1539_680']. No restart or new completion claim.

- 2026-09-30T22:46:57.585598+00:00: independently live Insula admitted scene 13619063687271391084_1519_680_1539_680, all retained publication/replay/eviction lineage reconciled. Snapshot 41/103, 1,398,599,868 points. Evidence `cohort-checkpoint-13619063687271391084_1519_680_1539_680-verified.json`; semantic linkage pending; scientific studies open.

- 2026-09-30T22:47:49.330072+00:00: host provenance reconciliation links scene 13619063687271391084_1519_680_1539_680 semantic support to independently live-audited lifecycle, retained reconstruction receipt, and publication report hash. All 20 admitted support captures now lifecycle-linked; split snapshot hash refreshed. Coverage only, no new live model experiment or scientific closure.

- 2026-09-30T22:49:10.770482+00:00: verified wait: existing sessions 64903 and 12631 polled live twice; authoritative driver child 4136578 confirmed (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 15628918650068847391_8077_670_8097_670 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-process`). Queue reconstructing scene 15628918650068847391_8077_670_8097_670; semantic capture awaiting completed reconstruction. No unadmitted checkpoint at initial inspection; no restart, cohort narrowing or scientific completion claim.

Read-only native scientific semantic support pilot passed for 15628918650068847391_8077_670_8097_670: 4237924 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T22:50:07.173607+00:00: session 12631 terminal exit 0; admitted scene 15628918650068847391_8077_670_8097_670 independent live valid-range semantic support: 4,237,924 eligible labels. Receipt/artifacts/current-code/source/manifest/reconstruction identities reconciled. Coverage 21/103, 95,053,662 labels, lifecycle linkage pending. Queue point reconstruction exit 0 and publication live; scientific studies remain open.

- 2026-09-30T22:51:25.252942+00:00: verified wait: queue session 64903 successful point publication for 15628918650068847391_8077_670_8097_670; independent replay child observed, same handle re-polled live. Current authoritative driver child 5262 confirmed (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/verify-scientific-replay.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/15628918650068847391_8077_670`). Capture session 43840 polled live. No full checkpoint at initial inspection; original cohort and running candidates preserved.

- 2026-09-30T22:52:47.369165+00:00: verified wait: queue session 64903 point replay/eviction exit 0 for 15628918650068847391_8077_670_8097_670; sidecar publication child 29914 confirmed live (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort`). Capture session 43840 polled live. Non-atomic working storage 14,812,625,533 bytes, 31,855 files; no peak or cap certification. No new checkpoint at initial inspection; scientific studies open.

- 2026-09-30T22:54:08.000487+00:00: verified wait: session 64903 polled live twice; authoritative driver child 60007 remains live (`bwrap --unshare-all --die-with-parent --ro-bind /data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v2 / --ro-bind /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception /experiment --ro-bin`). Scene 15628918650068847391_8077_670_8097_670 sidecar publication pending at initial inspection, no unadmitted checkpoint. Capture session 43840 polled live awaiting next completed reconstruction. Preserved current handles; no restart or scientific completion claim.

- 2026-09-30T22:55:23.085468+00:00: verified wait, queue session 64903 sidecar eviction exit 0 for 15628918650068847391_8077_670_8097_670; camera stage active. Authoritative driver child 88196 confirmed live (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/verify-camera-replay.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/15628918650068847391_8077_670_8097_670/came`). Capture session 43840 also polled live; no complete checkpoint at initial inspection, no restart or scientific completion claim.

- 2026-09-30T22:56:38.531321+00:00: verified wait: queue session 64903 polled live twice and driver child 98704 confirmed (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 14098575914252965554_511_000_531_000 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific`). Capture session 43840 polled live. Unadmitted full checkpoints now ['15628918650068847391_8077_670_8097_670']; independent camera replay pending at initial inspection. No restart or scientific completion claim.

- 2026-09-30T22:57:17.322549+00:00: independent live Insula admitted 15628918650068847391_8077_670_8097_670, retained publication/replay/eviction lineage reconciled. Snapshot 42/103, 1,429,750,057 points. Evidence `cohort-checkpoint-15628918650068847391_8077_670_8097_670-verified.json`; semantic linkage pending; scientific studies open.

- 2026-09-30T22:58:06.662298+00:00: scene 15628918650068847391_8077_670_8097_670 semantic support host-linked to independently live-audited checkpoint, retained reconstruction receipt and publication report hash. All 21 admitted captures now lifecycle-linked; split snapshot refreshed. Coverage-only provenance reconciliation, not a new live model experiment; scientific studies open.

Read-only native scientific semantic support pilot passed for 14098575914252965554_511_000_531_000: 4653467 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T22:59:27.615328+00:00: verified wait: sessions 64903/43840 polled live twice; driver PID 3958580 child 140749 confirmed (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-scene.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/14098575914252965554_511_000_`). Scene 14098575914252965554_511_000_531_000 reconstruction active, capture awaiting completed output. No new checkpoint at initial inspection; no job restart or scientific completion claim.

- 2026-09-30T23:00:02.139767+00:00: session 43840 terminal exit 0; scene 14098575914252965554_511_000_531_000 support admitted after receipt/artifact/current code/source/manifest/reconstruction identity checks. 4,653,467 new eligible labels, total 99,707,129 across 22/103; lifecycle linkage pending. Prior wait note preceded observed terminal output; this entry records terminal capture and passed reconstruction. Scientific studies open.

- 2026-09-30T23:01:21.744009+00:00: verified wait: queue session 64903 point publication exit 0 for 14098575914252965554_511_000_531_000; independent replay observed. Existing session re-polled live; authoritative driver child 174765 confirmed (`bwrap --unshare-all --die-with-parent --ro-bind /data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v2 / --ro-bind /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception /experimen`). Capture session 52247 polled live. No complete checkpoint at initial inspection; scientific scope unchanged, no restart.

- 2026-09-30T23:02:37.662633+00:00: verified wait: session 64903 point eviction exit 0 for 14098575914252965554_511_000_531_000; same queue re-polled live. Authoritative driver child 179290 confirmed (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/1409857591425296`). Capture session 52247 polled live awaiting next reconstruction. No full checkpoint at initial inspection; no restart or scientific completion claim.

- 2026-09-30T23:03:57.064498+00:00: verified wait: existing queue session 64903 polled live twice; authoritative driver child 271899 confirmed (`bwrap --unshare-all --die-with-parent --ro-bind /data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v2 / --ro-bind /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception /experiment --ro-bin`). Capture session 52247 polled live, waiting for next reconstruction. Sidecar publication for 14098575914252965554_511_000_531_000 active at initial inspection; no full checkpoint ready. No restart or narrowed research scope.

- 2026-09-30T23:05:15.786897+00:00: verified wait: existing session 64903 sidecar eviction exit 0 for 14098575914252965554_511_000_531_000; camera publication child observed. Driver child 350901 confirmed live (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 10734565072045778791_440_000_460_000 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/`). Capture session 52247 polled live. Unadmitted checkpoints ['14098575914252965554_511_000_531_000']; no restart or scientific completion claim.

- 2026-09-30T23:05:52.725738+00:00: independent live Insula admitted 14098575914252965554_511_000_531_000; retained publication/replay/eviction lineage reconciled. Snapshot 43/103, 1,462,794,342 points. Evidence `cohort-checkpoint-14098575914252965554_511_000_531_000-verified.json`; semantic linkage pending; scientific studies open.

- 2026-09-30T23:06:44.815229+00:00: host-linked 14098575914252965554_511_000_531_000 semantic support to independently live-audited checkpoint, retained reconstruction receipt and publication report hash; all 22 captures lifecycle-linked. Split snapshot refreshed. Coverage-only provenance reconciliation; scientific studies open.

- 2026-09-30T23:08:08.708572+00:00: verified wait: existing sessions 64903/52247 polled live twice; authoritative driver child 350901 confirmed (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 10734565072045778791_440_000_460_000 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific`). Scene 10734565072045778791_440_000_460_000 reconstruction active at initial inspection; no new full checkpoint. Running handles preserved, no restart or scientific completion claim.

Read-only native scientific semantic support pilot passed for 10734565072045778791_440_000_460_000: 4794569 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T23:09:03.618691+00:00: session 52247 terminal exit 0; admitted independent live semantic support for 10734565072045778791_440_000_460_000: 4,794,569 eligible labels. Receipt/artifacts/current-code/source/manifest/reconstruction identities reconciled. Coverage 23/103, 104,501,698 labels; lifecycle linkage pending. Queue reconstruction exit 0; scientific studies remain open.

- 2026-09-30T23:10:20.874951+00:00: verified wait: session 64903 polled live twice; scene 10734565072045778791_440_000_460_000 point publication active at initial inspection. Driver child 494050 confirmed live (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/verify-scientific-replay.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/10734565072045778791_440_000_`). Capture session 56185 also polled live awaiting next reconstruction. No complete checkpoint initially; existing jobs preserved, scientific studies open.

- 2026-09-30T23:11:37.274256+00:00: verified wait: queue session 64903 polled live twice; independent point replay for 10734565072045778791_440_000_460_000 active at initial inspection. Authoritative driver child 530942 confirmed live (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/10734565072045778791_440_0`). Capture session 56185 polled live. No full checkpoint at initial inspection; existing handles preserved, scientific studies open.

- 2026-09-30T23:12:54.479255+00:00: verified wait: session 64903 polled live twice; process tree confirmed Waystone/native HDFS sidecar upload for 10734565072045778791_440_000_460_000. Current driver child 530942 confirmed (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/1073456507204577`). Capture session 56185 polled live. No full checkpoint at initial inspection; no restart or scientific completion claim.

- 2026-09-30T23:14:09.058391+00:00: verified wait: original session 64903 polled live twice; authoritative driver child 586351 confirmed (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-camera.py --evidence /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/10734565072045778`). Initial child turnover yielded no child command, not terminal evidence; same queue retained and re-polled. Capture session 56185 live. No full checkpoint at initial inspection; scientific studies open.

- 2026-09-30T23:15:29.617351+00:00: verified wait: session 64903 camera publication exit 0 for 10734565072045778791_440_000_460_000; camera replay active at initial inspection. Driver child 607601 confirmed live (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/scientific-preprocess.py --scene 2681180680221317256_1144_000_1164_000 --output /data02/home/philip.yang/.cache/waystone/waymo-perception`). Capture session 56185 polled live. Unadmitted checkpoints ['10734565072045778791_440_000_460_000']; no restart or scientific completion claim.

- 2026-09-30T23:16:08.131022+00:00: independent live Insula admitted 10734565072045778791_440_000_460_000; retained publication/replay/eviction lineage reconciled. Snapshot 44/103, 1,498,754,230 points. Evidence `cohort-checkpoint-10734565072045778791_440_000_460_000-verified.json`; semantic linkage pending; scientific studies open.

- 2026-09-30T23:17:00.849442+00:00: host-linked 10734565072045778791_440_000_460_000 semantic support to independently live-audited checkpoint, retained reconstruction receipt and publication report hash; all 23 admitted captures lifecycle-linked. Split snapshot refreshed. Coverage-only provenance reconciliation; scientific studies open.

Read-only native scientific semantic support pilot passed for 2681180680221317256_1144_000_1164_000: 4196717 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T23:18:41.565744+00:00: verified wait: sessions 64903/56185 polled live; original driver PID 3958580 cmdline independently reconfirmed. Child turnover caused a host assertion with no writes; same session re-polled, not restarted. Current child PIDs ['759989']. No new checkpoint at initial inspection; scientific studies open.

- 2026-09-30T23:19:30.259132+00:00: session 56185 terminal exit 0; admitted independent live valid-range semantic support for 2681180680221317256_1144_000_1164_000: 4,196,717 eligible labels after artifact/current code/source/manifest/reconstruction receipt checks. Coverage 24/103, 108,698,415 labels; lifecycle linkage pending. Queue session 64903 live; scientific studies open.

- 2026-09-30T23:20:51.639744+00:00: verified wait: queue session 64903 point publication exit 0 for 2681180680221317256_1144_000_1164_000; independent replay observed. Same handle re-polled live, driver child 828147 confirmed (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/2681180680221317256_1144_0`). Capture session 17639 polled live. No full checkpoint at initial inspection; no restart or scientific completion claim.

- 2026-09-30T23:22:06.330429+00:00: verified wait: existing session 64903 polled live twice; authoritative driver child 828147 confirmed (`python3 /data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception/publish-scientific-sidecars.py /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1/2681180680221317256_1144_0`). Scene 2681180680221317256_1144_000_1164_000 sidecar publication pending at initial inspection; no unadmitted full checkpoint. Capture session 17639 polled live awaiting reconstruction. No restart or scientific completion claim.

- 2026-09-30T23:23:26.849065+00:00: verified wait: session 64903 polled live twice; original driver PID 3958580 cmdline confirmed, children ['873673']. Scene 2681180680221317256_1144_000_1164_000 sidecar publication process tree performing Waystone/native HDFS readback at initial inspection (not upload). Capture session 17639 polled live. No complete checkpoint initially; no restart or scientific completion claim.

- 2026-09-30T23:24:48.174570+00:00: verified wait: session 64903 sidecar eviction exit 0 for 2681180680221317256_1144_000_1164_000; camera preprocessing observed live. Existing handle re-polled; authoritative driver PID 3958580 confirmed, children ['884058']. Capture session 17639 live. Unadmitted checkpoints []; no restart or scientific completion claim.

- 2026-09-30T23:25:52.024659+00:00: independent live Insula admitted 2681180680221317256_1144_000_1164_000; retained publication/replay/eviction lineage reconciled. Snapshot 45/103, 1,530,037,780 points. Evidence `cohort-checkpoint-2681180680221317256_1144_000_1164_000-verified.json`; semantic linkage pending; scientific studies open.

- 2026-09-30T23:26:44.177735+00:00: host-linked 2681180680221317256_1144_000_1164_000 semantic support to independently live-audited checkpoint, retained reconstruction receipt and publication report hash; all 24 admitted captures lifecycle-linked. Split snapshot refreshed. Coverage-only provenance reconciliation; scientific studies open.

Read-only native scientific semantic support pilot passed for 8722413665055769182_2840_000_2860_000: 5351677 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T23:28:30.972868+00:00: verified wait: existing sessions 64903/17639 polled live twice; authoritative driver PID 3958580 cmdline confirmed, children ['952991']. Scene 8722413665055769182_2840_000_2860_000 reconstruction active at initial inspection; capture awaiting output. No unadmitted checkpoint initially, no restart or scientific completion claim.

- 2026-09-30T23:29:13.232206+00:00: session 17639 terminal exit 0; admitted independent live semantic support for 8722413665055769182_2840_000_2860_000: 5,351,677 eligible labels, total 114,050,092 across 25/103, after receipt/artifact/source/manifest/current-code/reconstruction checks. Lifecycle linkage pending. Earlier wait entry preceded terminal output; reconstruction passed and queue remains live. Scientific studies open.

- 2026-09-30T23:30:30.951285+00:00: verified wait: queue session 64903 polled live twice; point publication for 8722413665055769182_2840_000_2860_000 observed live. Authoritative driver PID 3958580 cmdline confirmed, child PIDs ['964485']. Capture session 91110 polled live awaiting next reconstruction. No full checkpoint at initial inspection, no restart or scientific completion claim.

- 2026-09-30T23:31:46.916238+00:00: verified wait: existing queue session 64903 polled live twice; independent point replay for 8722413665055769182_2840_000_2860_000 observed. Authoritative driver PID 3958580 cmdline confirmed, child PIDs ['972324']. Capture session 91110 polled live waiting. No full checkpoint initially; no restart or scientific completion claim.

- 2026-09-30T23:33:07.463311+00:00: verified wait: existing session 64903 polled live twice; process tree confirmed Waystone/native HDFS sidecar upload for 8722413665055769182_2840_000_2860_000. Authoritative driver PID 3958580 cmdline confirmed, children ['972324']. Capture session 91110 polled live awaiting next reconstruction; no unadmitted checkpoint initially. No restart or scientific completion claim.

- 2026-09-30T23:34:27.585568+00:00: verified wait: session 64903 sidecar publication exit 0 for 8722413665055769182_2840_000_2860_000; live Insula child observed. Same handle re-polled live, authoritative driver PID 3958580 cmdline confirmed, children ['1009114']. Capture session 91110 polled live; no full checkpoint at initial inspection. No restart or scientific completion claim.

- 2026-09-30T23:35:46.701759+00:00: verified wait: session 64903 camera publication exit 0 for 8722413665055769182_2840_000_2860_000; same handle re-polled live. Authoritative driver PID 3958580 cmdline confirmed, children ['1024121']; capture session 91110 live. Unadmitted checkpoints ['8722413665055769182_2840_000_2860_000']; no restart or scientific completion claim.

- 2026-09-30T23:36:26.569973+00:00: independent live Insula admitted 8722413665055769182_2840_000_2860_000; retained publication/replay/eviction lineage reconciled. Snapshot 46/103, 1,568,838,693 points. Evidence `cohort-checkpoint-8722413665055769182_2840_000_2860_000-verified.json`; semantic linkage pending; scientific studies open.

- 2026-09-30T23:37:17.151255+00:00: host-linked 8722413665055769182_2840_000_2860_000 semantic support to independently live-audited checkpoint, retained reconstruction receipt and publication report hash; all 25 admitted captures lifecycle-linked. Split snapshot refreshed. Coverage-only provenance reconciliation; scientific studies open.

- 2026-09-30T23:38:44.805735+00:00: verified wait: existing sessions 64903/91110 polled live twice; authoritative driver PID 3958580 cmdline confirmed, children ['1024121']. Scene 12012663867578114640_820_000_840_000 reconstruction active at initial inspection; capture waiting for completed output. No full checkpoint initially, no restart or scientific completion claim.

Read-only native scientific semantic support pilot passed for 12012663867578114640_820_000_840_000: 4773540 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T23:39:40.726984+00:00: session 91110 terminal exit 0; admitted independent live semantic support for 12012663867578114640_820_000_840_000: 4,773,540 eligible labels after receipt/artifact/current-code/source/manifest/reconstruction checks. Coverage 26/103, 118,823,632 labels; lifecycle linkage pending. Queue reconstruction exit 0 and publication live; scientific studies open.

- 2026-09-30T23:41:04.330846+00:00: verified wait: existing queue session 64903 polled live twice; scene 12012663867578114640_820_000_840_000 point publication active at initial inspection. Authoritative driver PID 3958580 cmdline confirmed, children ['1072546']; capture session 23014 polled live awaiting next reconstruction. No full checkpoint initially; no restart or scientific completion claim.

- 2026-09-30T23:42:26.853450+00:00: verified wait: session 64903 point replay/eviction exit 0 for 12012663867578114640_820_000_840_000; sidecar publication observed live. Same handle re-polled, authoritative driver PID 3958580 cmdline confirmed, children ['1084962']. Capture session 23014 polled live; no full checkpoint initially. No restart or scientific completion claim.

- 2026-09-30T23:43:45.196214+00:00: verified wait: existing session 64903 polled live twice; process tree confirmed Waystone/native HDFS sidecar upload for 12012663867578114640_820_000_840_000. Authoritative driver PID 3958580 cmdline confirmed, children ['1084962']; capture session 23014 live awaiting next reconstruction. No full checkpoint initially; no restart or scientific completion claim.

- 2026-09-30T23:45:02.846514+00:00: verified wait: queue session 64903 sidecar publication exit 0 for 12012663867578114640_820_000_840_000; live Insula child observed. Same handle re-polled; authoritative driver PID 3958580 cmdline confirmed, children ['1118367']. Capture session 23014 polled live; no full checkpoint initially. No restart or scientific completion claim.

- 2026-09-30T23:46:27.134876+00:00: verified wait: session 64903 polled live twice; authoritative driver PID 3958580 cmdline confirmed, children ['1125931']. Capture session 23014 live awaiting next reconstruction. Unadmitted checkpoints ['12012663867578114640_820_000_840_000']; no restart or scientific completion claim.

- 2026-09-30T23:47:07.539050+00:00: independent live Insula admitted 12012663867578114640_820_000_840_000; retained publication/replay/eviction lineage reconciled. Snapshot 47/103, 1,604,280,404 points. Evidence `cohort-checkpoint-12012663867578114640_820_000_840_000-verified.json`; semantic linkage pending; scientific studies open.

- 2026-09-30T23:48:00.093783+00:00: host-linked 12012663867578114640_820_000_840_000 semantic support to independently live-audited checkpoint, retained reconstruction receipt and publication report hash; all 26 admitted captures lifecycle-linked. Split snapshot refreshed. Coverage-only provenance reconciliation; scientific studies open.

Read-only native scientific semantic support pilot passed for 9907794657177651763_1126_570_1146_570: 3031779 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-09-30T23:49:20.286411+00:00: verified wait: existing sessions 64903/23014 polled live twice; authoritative driver PID 3958580 cmdline confirmed, children []. Scene 9907794657177651763_1126_570_1146_570 reconstruction active at initial inspection; capture awaiting completed output. No new full checkpoint initially; no restart or scientific completion claim.

- 2026-09-30T23:49:53.794220+00:00: session 23014 terminal exit 0; admitted independent live semantic support for 9907794657177651763_1126_570_1146_570: 3,031,779 eligible labels after receipt/artifact/current-code/source/manifest/reconstruction checks. Coverage 27/103, 121,855,411 labels; lifecycle linkage pending. Earlier wait entry preceded terminal capture output; scientific studies open.

- 2026-09-30T23:51:14.824124+00:00: verified wait: existing session 64903 polled live twice; point publication for 9907794657177651763_1126_570_1146_570 observed. Authoritative driver PID 3958580 cmdline confirmed, children ['1228320']; capture session 93013 polled live awaiting reconstruction. No full checkpoint initially; no restart or scientific completion claim.

- 2026-09-30T23:52:34.455841+00:00: verified wait: existing session 64903 polled live twice; live Insula child observed for scene 9907794657177651763_1126_570_1146_570. Authoritative driver PID 3958580 cmdline confirmed, children ['1235368']; capture session 93013 polled live awaiting reconstruction. No full checkpoint initially; no restart or scientific completion claim.

- 2026-09-30T23:53:59.455927+00:00: verified wait: session 64903 polled live twice; process tree confirmed Waystone/native HDFS sidecar upload for 9907794657177651763_1126_570_1146_570. Authoritative driver PID 3958580 cmdline confirmed, children ['1235368']; capture session 93013 polled live awaiting next reconstruction. No full checkpoint initially; no restart or scientific completion claim.

- 2026-09-30T23:55:29.610054+00:00: authoritative queue interruption: session 64903 unknown, /proc/3958580 missing, process search finds no queue/publisher/capture workers. No new full checkpoint. Preserved scene 9907794657177651763_1126_570_1146_570 partial artifacts and hashed 28439 small JSON recovery files; `cohort-interruption-recovery-observation.json`. Did not restart or admit incomplete lifecycle. Next action is bounded partial-publication recovery and restoring queue/capture after resource/identity checks.


### Interrupted sidecar publication — fresh audit launched

Process inspection confirmed no cohort, publisher, or capture worker. The interrupted scene retains a 7,176,837,120-byte bundle containing 56,807 files, both publication manifests, and the prior independent bundle report; publisher receipt is absent. Logs alone are not admitted as a completed publication. A fresh offline live Insula archive/content/provenance and manifest-equality audit is running through exec session 11707; its invocation and eventual exit status are retained under `~/.cache/waystone/waymo-perception/insula/sidecar-interruption-recheck-9907794657177651763_1126_570_1146_570`. An initial detached attempt disappeared without output and is not accepted as evidence; the foreground session is the authoritative attempt. Cohort count remains 47/103. Recovery and scientific comparisons remain open.

The foreground fresh live audit finished with exit 0: all 56,807 decoded files reconciled, archive digest matched, provenance matched trusted inputs, and retained publication manifests matched. Evidence: `research/interrupted-sidecar-fresh-live-check.json`. Missing publisher receipt and complete scene lifecycle remain unadmitted.


### Interrupted publication recovery — original publisher rerun

Verified the fresh live audit artifact hashes, the 7,176,837,120-byte archive digest, and all 56,807 decoded source files against the retained trusted inventory. Removed only the redundant archive copy; preserved interrupted metadata and logs under `sidecar-publication-interrupted`. Recovery record: `research/interrupted-sidecar-republication-recovery.json`. The original unchanged `publish-scientific-sidecars.py` is running under authoritative exec session 72815 to regenerate a complete publication with fresh pack/HDFS readback/independent live validation. Its invocation, log and eventual exit status are retained in the scene directory. Queue ownership lock is held throughout recovery. No original receipt was fabricated; admitted scene count remains 47/103 pending complete lifecycle and independent checkpoint audit.

Publication rerun session 72815 terminated with exit 1 after successful live packing: Waystone refuses an existing content-addressed HDFS destination without explicit overwrite. No completed publisher receipt was admitted. Session 86484 now holds the queue lock and is reading back the existing HDFS object, requiring its exact archive digest before allowing identical-byte archive overwrite; manifest overwrite additionally requires equality to the preserved original manifest digest. Current original publisher source is unchanged. HDFS get process 1487331 and native HDFS child 1488062 were confirmed live. Failed-rerun metadata is preserved; no completed-scene count change.

Existing HDFS object readback finished with exit 0 and exact 8f49152157c40e473a0326c3f00138842b51fd88db21d705b731965389752c7a archive digest (7,176,837,120 bytes). Evidence: `research/interrupted-sidecar-existing-hdfs-readback.json`. Original publisher rerun session 86484 passed pack-live and continues under ownership lock. Recovery successor session 18346 is queued on that lock: it requires the new complete publisher receipt/current candidates/artifact hashes/runtime identity, then performs original live Insula sidecar eviction and original camera preprocessing. It cannot proceed from a failed or absent publication receipt. Scene still unadmitted pending complete lifecycle and independent checkpoint audit.

Recovery publication session 86484 finished successfully with a complete original-publisher receipt. All six checks passed, including fresh HDFS upload/readback and independent live bundle validation. Session 18346 then performed verified live Insula sidecar eviction (14,297,253,405 bytes) and started native camera preprocessing. Surviving publisher artifacts/current candidates and deleted-artifact digests were host-reconciled against the eviction receipt; research evidence: `research/interrupted-sidecar-publication-recovered.json`. Session 89042 queues camera publication/two independent replay checks/live eviction behind the same ownership lock, requiring successful native camera preprocessing first. Full scene checkpoint and cohort admission remain open; count unchanged at 47/103.

Camera preprocessing session 18346 completed with exit 0; camera_image, camera_segmentation and camera_box each have successful native decode and independent-check receipts. Successor publication/replay/eviction session 89042 confirmed live. No full scene admission yet.

Recovered scene 9907794657177651763_1126_570_1146_570 passed independent live Insula checkpoint audit: 36 retained documents, 16 worker receipts, 3 verified evictions, 87,727 evicted artifacts. Its 1,990 point records / 33,246,788 points were admitted into the external checkpoint registry and progress snapshot: 48/103 scenes, 1,637,527,192 points, 46 camera scenes. The unchanged original driver was restored for exactly 55 untouched original scenes under exec session 12739 (no pre-existing partial directories). Read-only native semantic support capture restored under authoritative exec session 22422; helper SHA retained unchanged. Scientific models/protocol/comparisons remain open.

Recovered scene semantic-support lineage linked to independent checkpoint/source point publication: 3,031,779 eligible labels. Verified all 27 linkage evidence chains. Corrected split summary linkage count: earlier summary counted only literal `linked` strings and omitted 17 equivalently proven entries; counts now derive from digest-verified linkage evidence. Training support remains 27 scenes / 121,855,411 labels, now all 27 lifecycle-linked; development/validation coverage remains open. This is host provenance reconciliation, not a new scientific experiment.

Read-only native scientific semantic support pilot passed for 13807633218762107566_6625_000_6645_000: 4161502 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

New restored-queue native semantic support admitted for 13807633218762107566_6625_000_6645_000: 4,161,502 eligible labels / 30 labeled timestamps. Verified live receipt, artifacts, current helper/orchestrator, original source and reconstruction/report identity. Aggregate now 28/103 scenes, 126,016,913 labels; 27 lifecycle-linked, this scene pending final checkpoint. Queue driver PID 1609839 and sessions 12739/22422 confirmed live.

Verified wait: first restored scene point publication finished with all checks passing; prior publisher observation raced with normal stage completion and was not treated as queue termination. Current cohort/replay processes confirmed live through /proc and queue session 12739 polled successfully. No new full-scene checkpoint admission.

Verified wait: restored scene 13807633218762107566_6625_000_6645_000 completed point publication, two independent point replays, and verified point eviction. Current queue/sidecar publisher processes confirmed live through /proc. No full scene checkpoint exists yet. Ticket 07 still requires all cohort task eligibility, 64-source native training box distributions, actual training/evaluation resource measurements and numerical preregistration before comparisons; processing progress does not close those gates.

Verified wait: sidecar publisher PID 1846214 and HDFS upload PID 1852671 confirmed live; queue/capture sessions 12739/22422 polled. Bounded 30-second wait followed by queue repoll and stage inspection; no completed full checkpoint to admit. No restart or cohort reduction.

Verified wait advanced first restored scene through successful sidecar publication/verified eviction and native camera preprocessing/publication (all three camera components decode+independent-check receipts passed). Queue session 12739 confirmed live; separate independent checkpoint audit queued behind actual checkpoint availability, requiring live original PID 1609839 until receipt arrives. External source17/manifest/runtime/helper pins and original independent checkpoint checker remain required. Counts not promoted from partial stages.

Independent live checkpoint audit for 13807633218762107566_6625_000_6645_000 passed: 30 retained files, 16 workers, 3 verified evictions. Added 30,031,984 points to admitted cohort totals: 49/103 scenes, 1,667,559,176 points, 47 camera scenes. Semantic capture/report/publication/source lineage linked; all 28 observed support scenes now linked, 126,016,913 eligible labels. Queue session 12739 remains live; scientific protocol/comparisons open.

Verified wait: restored queue advanced to native scene 7850521592343484282_4576_090_4596_090. Queue and capture sessions 12739/22422 polled successfully; processing worker processes confirmed through /proc after bounded 30-second observation. Completed native component receipts inspected, but no new full checkpoint admitted. Original 103-scene scope and scientific gates retained.

Read-only native scientific semantic support pilot passed for 7850521592343484282_4576_090_4596_090: 2960324 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Verified wait advanced to complete reconstruction and successful live semantic capture for 7850521592343484282_4576_090_4596_090. Receipt/artifacts/current consumer and capture helper/source/report identities reconciled before promotion. Added 2,960,324 eligible labels across 20 timestamps. Aggregate 29/103 scenes / 128,977,237 labels; 28 linked, current scene pending independently admitted full lifecycle. Queue/capture remain live.

Verified wait for 7850521592343484282_4576_090_4596_090: current live processes observed and queue session 12739 polled before/after bounded 30-second interval. Passed publication/replay receipt stages: {'point-publication': 6, 'point-replay': 2}. Accounted scientific working set 7,876,320,707 bytes, within proposed 15 GiB cap; no competing raw staging introduced. Full checkpoint admission remains pending.

Verified wait: original queue and capture handles 12739/22422 confirmed live, followed by bounded 30-second observation and queue repoll. Current sidecar publisher/HDFS and queue processes rechecked through /proc; no completed full checkpoint is available for admission. No queue restart, staging overlap, reduced cohort or scientific completion claim.

Verified wait: scene 7850521592343484282_4576_090_4596_090 sidecar upload advanced to retained hdfs-put stage log; publication continues toward mirror/independent check. Queue session 12739 polled before and after bounded 30-second observation, current processes revalidated through /proc. No new full-scene checkpoint.

Verified wait: polled queue session 12739 before/after bounded 30-second interval; rechecked current original lifecycle processes through /proc and sidecar receipt availability. No timeout-based restart or full scene admission.

Verified wait: current scene camera publication completed; original queue session 12739 remains live. Independent full checkpoint auditor session 51895 queued for scene 7850521592343484282_4576_090_4596_090, watching actual original driver PID 1609839 until checkpoint availability and preserving source17/runtime/manifest/helper/checkpoint pins. No checkpoint-count promotion before live audit succeeds.

Independent checkpoint auditor 51895 finished exit 0: 30 retained files, 16 worker receipts and 3 verified evictions. Scene 7850521592343484282_4576_090_4596_090 admitted; totals 50/103 scenes, 1,700,867,311 points, 48 camera scenes. Native semantic support lifecycle linkage for this scene remains to reconcile separately. Scientific comparisons remain open.

Native semantic support for scene 7850521592343484282_4576_090_4596_090 linked by source/reconstruction/report/publication digests to independently admitted checkpoint. All 29 observed semantic scenes now lifecycle-linked, totaling 128,977,237 eligible labels. Host lineage reconciliation only, no new model experiment or scientific closure. Queue/capture sessions 12739/22422 confirmed live.

Read-only native scientific semantic support pilot passed for 12303641360375776820_4378_000_4398_000: 4365603 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Verified wait for native scene 12303641360375776820_4378_000_4398_000: all seven sidecar component receipts present; original cohort/reconstruction processes confirmed live through /proc and both sessions 12739/22422 polled around a bounded observation interval. No new full-scene admission or unsupported scientific claim.

Promoted native semantic-support receipt for 12303641360375776820_4378_000_4398_000 after live check/artifact/current helper/source/reconstruction/report verification: 4,365,603 eligible labels. Aggregate 30/103 scenes, 133,342,840 labels; 29 lifecycle-linked, current capture pending full-scene checkpoint.

Verified wait: original scene 12303641360375776820_4378_000_4398_000 point preprocessing completed and point publication is active. Queue session 12739 polled before/after bounded 30-second observation; current queue/publisher/HDFS processes confirmed through /proc. No complete checkpoint ready for admission; scientific scope retained.

Verified wait for original point publication/replay: queue and semantic capture sessions 12739/22422 polled, current lifecycle process identities confirmed through /proc after a bounded observation interval. No full checkpoint admitted, no restart or resource/scope change.

Verified wait: scene 12303641360375776820_4378_000_4398_000 passed receipt stages {'point-publication': 6, 'point-replay': 2}; verified point eviction completed=True. Current queue/replay/publication process identities confirmed via /proc after queue polling and bounded 30-second observation. No full-scene admission or scientific gate closure.

Verified wait: original queue/capture handles 12739/22422 polled; sidecar publisher/HDFS stage processes confirmed live through /proc after bounded 30-second observation. No completed scene checkpoint available. Scientific studies and original cohort scope retained unchanged.

Verified wait: queue session 12739 polled around bounded 30-second observation; original sidecar/camera lifecycle processes verified live through /proc. Publication logs/receipt inspected without treating partial logs as completion. No new full-scene checkpoint admitted.

Verified wait: current scene camera preprocessing completed; full independent checkpoint auditor session 63847 queued for 12303641360375776820_4378_000_4398_000, requiring actual original driver PID 1609839 until checkpoint availability. Queue session 12739 remains live after bounded observation; no checkpoint-count promotion before independent live verification.

Independent live checkpoint auditor 63847 finished successfully: 30 retained files, 16 workers, 3 verified evictions. Scene 12303641360375776820_4378_000_4398_000 admitted; totals 51/103 scenes, 1,731,993,194 points, 49 camera scenes. Semantic lifecycle linkage remains to reconcile separately. Scientific comparisons remain open.

Semantic support for scene 12303641360375776820_4378_000_4398_000 linked by exact source/reconstruction/report/publication digests to independently admitted lifecycle. All 30 observed support scenes now linked, totaling 133,342,840 eligible labels. Host provenance reconciliation only; original cohort and scientific gates unchanged. Queue/capture sessions 12739/22422 confirmed live.

Verified wait: native scene 2415873247906962761_5460_000_5480_000 has all seven sidecar worker receipts; current original reconstruction/cohort processes confirmed through /proc. Both queue/capture sessions polled and rechecked after bounded 30-second observation. No partial stage or absent receipt promoted to scene/scientific completion.

Read-only native scientific semantic support pilot passed for 2415873247906962761_5460_000_5480_000: 4845820 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Native semantic support admitted for 2415873247906962761_5460_000_5480_000: 4,845,820 eligible labels / 30 timestamps. Live receipt/artifacts/current helpers/native source/reconstruction/report identities checked; aggregate 31/103 scenes / 138,188,660 labels. 30 lifecycle-linked, newest scene pending full checkpoint. Queue/capture sessions 12739/22422 confirmed live. No scientific configuration freeze or model comparison.

Verified wait: scene 2415873247906962761_5460_000_5480_000 completed native reconstruction and is in point publication/replay lifecycle. Original queue session 12739 polled around bounded 30-second observation; active queue/publisher/HDFS process identities confirmed through /proc. Full checkpoint pending; scientific gates unchanged.

Verified wait: scene 2415873247906962761_5460_000_5480_000 has passed receipt stages {'point-publication': 6, 'point-replay': 2}; completed verified point eviction=True. Queue/capture sessions 12739/22422 polled around bounded observation; current lifecycle processes rechecked through /proc. No full checkpoint admission or scientific gate closure.

Verified wait: current sidecar publication/transfer processes confirmed live through /proc after queue session 12739 polling and bounded 30-second observation. Accounted scientific working set 15,102,542,161 bytes, within proposed 15 GiB cap. No new completed scene checkpoint or scientific result.

Verified wait: queue session 12739 polled around bounded observation; current original publisher/camera lifecycle process identities revalidated through /proc. Sidecar receipt checked separately from stage logs. No full scene checkpoint admitted or scientific closure.

Verified wait: original camera lifecycle for scene 2415873247906962761_5460_000_5480_000 continues under queue session 12739. Independent auditor session 46888 queued behind actual checkpoint availability, requiring original live driver PID until receipt exists and full source17/runtime/helper/manifest pins before audit. Both sessions polled after bounded observation. No checkpoint promotion before audit succeeds.

Independent live checkpoint audit 46888 passed: 30 retained files, 16 workers, 3 verified evictions. Scene 2415873247906962761_5460_000_5480_000 admitted; totals 52/103 scenes, 1,768,210,505 points, 50 camera scenes. Semantic lifecycle linkage remains to reconcile; scientific comparisons open.

Semantic support for scene 2415873247906962761_5460_000_5480_000 linked to independently admitted lifecycle with exact native source/reconstruction/report/publication identity checks. All 31 observed support scenes now linked, totaling 138,188,660 eligible labels. Host lineage reconciliation only; scientific studies remain open. Queue/capture handles 12739/22422 confirmed live.

Verified wait: original next scene 2656110181316327570_940_000_960_000 has seven completed sidecar worker receipts and current reconstruction/cohort processes confirmed via /proc. Original queue/capture handles 12739/22422 polled successfully around bounded observation. No new unadmitted checkpoints; 103-scene scope retained.

Read-only native scientific semantic support pilot passed for 2656110181316327570_940_000_960_000: 4731732 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Native semantic support admitted for 2656110181316327570_940_000_960_000: 4,731,732 eligible labels / 30 timestamps. Live receipt/artifact/current helper/source/reconstruction/report identities reconciled before aggregate promotion. Coverage 32/103 scenes / 142,920,392 labels; 31 lifecycle-linked, current scene awaiting full checkpoint. Queue/capture sessions 12739/22422 confirmed live. Scientific comparisons remain open.

Verified wait: original point lifecycle for 2656110181316327570_940_000_960_000 remains active, with queue session 12739 polled before/after bounded observation and current lifecycle process identities rechecked through /proc. No unadmitted full checkpoints observed; no scientific gate closure or cohort reduction.

Verified wait: current scene 2656110181316327570_940_000_960_000 passed stages {'point-publication': 6, 'point-replay': 2}, verified point eviction completed=True. Original queue/capture handles 12739/22422 polled around bounded observation; current lifecycle process identities verified via /proc. Full scene checkpoint and scientific comparisons remain open.

Verified wait: current original sidecar publisher/HDFS and queue processes confirmed live through /proc after queue session 12739 polls and bounded observation. Scientific working set 15,146,502,053 bytes within proposed 15 GiB cap. No full checkpoint ready for admission; original cohort/scientific obligations retained.

Verified wait: queue session 12739 polled around bounded 30-second observation; current publisher/camera lifecycle processes confirmed through /proc and sidecar receipt checked. No new full-scene admission or scientific gate closure.

Verified wait: independent live checkpoint auditor 87820 queued for scene 2656110181316327570_940_000_960_000 behind actual original checkpoint availability; source17/manifest/runtime/current helper pins required. Original queue session 12739 and auditor polled after bounded 30-second observation. No admission before successful independent evidence.

Independent live checkpoint auditor 87820 passed: 30 retained files, 16 workers, 3 verified evictions. Scene 2656110181316327570_940_000_960_000 admitted; totals 53/103 scenes, 1,804,387,550 points, 51 camera scenes. Semantic lineage reconciliation remains separate; scientific studies open.

Semantic support for scene 2656110181316327570_940_000_960_000 linked to independently admitted lifecycle with exact source/reconstruction/report/publication identity checks. All 32 observed semantic scenes now lifecycle-linked, totaling 142,920,392 eligible labels. Host provenance reconciliation only; scientific studies remain open. Queue/capture sessions 12739/22422 confirmed live.

Verified wait: original scene 16473613811052081539_1060_000_1080_000 processing/cohort identities confirmed via /proc after queue/capture polling and bounded observation. No ready full checkpoint or promoted absent support receipt. Scientific studies and original cohort unchanged.

Read-only native scientific semantic support pilot passed for 16473613811052081539_1060_000_1080_000: 4756964 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Verified wait: original reconstruction/cohort processes confirmed live through /proc after polling queue/capture sessions 12739/22422 and bounded observation. No unavailable support or scene checkpoint promoted, no timeout-based restart or scientific scope reduction.

New native semantic-support receipt for 16473613811052081539_1060_000_1080_000 verified against live checks/artifacts/current helper/source/reconstruction/report identity before aggregate promotion: 4,756,964 eligible labels. Coverage 33/103 scenes / 147,677,356 labels; 32 lifecycle-linked, newest scene pending full checkpoint. No scientific closure.

Verified wait: native scene 16473613811052081539_1060_000_1080_000 passed stages {'point-publication': 6, 'point-replay': 2}; verified point eviction completed=False. Queue session 12739 polled around bounded observation and current lifecycle processes confirmed through /proc. No new full checkpoint admission or scientific scope change.

Verified wait: current scene point eviction completed and sidecar publication continues; queue/capture sessions 12739/22422 polled around bounded observation. Current original queue/publisher/HDFS identities confirmed via /proc. No new full checkpoint or scientific completion claim.

Verified wait: original sidecar publication/HDFS and queue processes revalidated through /proc after polling authoritative session 12739 and bounded observation. No new full checkpoint ready; partial stage logs not promoted as scientific evidence.

Verified wait: independent original full checkpoint auditor session 4161 queued for scene 16473613811052081539_1060_000_1080_000 behind actual receipt availability, watching confirmed original driver PID 1609839 and requiring source17/runtime/manifest/current helper pins. Queue and auditor handles polled after bounded observation; no count promotion before independent audit passes.

Independent live checkpoint auditor 4161 passed: 30 retained files, 16 workers, 3 verified evictions. Scene 16473613811052081539_1060_000_1080_000 admitted; totals 54/103 scenes, 1,840,118,072 points, 52 camera scenes. Semantic lineage reconciliation remains separate; scientific studies open.

Semantic support for scene 16473613811052081539_1060_000_1080_000 linked to independently admitted lifecycle with exact source/reconstruction/report/publication checks. All 33 observed support scenes now linked, totaling 147,677,356 eligible labels. Host provenance reconciliation only; scientific comparisons remain open. Queue/capture handles 12739/22422 confirmed live.

Verified wait: original scene 16646502593577530501_4878_080_4898_080 processing/cohort identities confirmed live via /proc after queue/capture polling and bounded observation. No full checkpoint ready; absent support receipt not promoted, no restart or scope reduction.

Read-only native scientific semantic support pilot passed for 16646502593577530501_4878_080_4898_080: 3586357 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Verified wait: original scene 16646502593577530501_4878_080_4898_080 native processing/cohort confirmed live via /proc after queue/capture polling around bounded observation. No reconstruction/support receipt promoted before completion; no restart or scientific scope reduction.

Native semantic support for 16646502593577530501_4878_080_4898_080 admitted after live receipt/artifact/current helper/source/reconstruction/report verification: 3,586,357 eligible labels. Coverage 34/103 scenes / 151,263,713 labels; 33 lifecycle-linked, newest awaiting full checkpoint. Scientific comparisons remain open.

2026-10-01T01:25:27.707481+00:00: independently admitted scene 16646502593577530501_4878_080_4898_080: 1,990 records, 39,261,178 points; live Insula reconciled 16 workers, 30 retained files, 3 verified evictions. Original cohort unchanged; 55/103 admitted, 1,879,379,250 points. Semantic lifecycle linkage and scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 7921369793217703814_1060_000_1080_000: 5012110 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

2026-10-01T01:36:41.161154+00:00: independently admitted 7921369793217703814_1060_000_1080_000; live Insula reconciled 16 workers, 30 retained files, 3 verified evictions; {'records': 1980, 'points': 37687242, 'identity_array_digest': '4d65cf901f4bf489884072a6b1028ce9ecab9c1c371ce92e6d1b652d82e005c1', 'status': 'all returned arrays independently match verified source point records'}. Original 103-scene cohort unchanged; scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 9385013624094020582_2547_650_2567_650: 3274975 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

2026-10-01T01:46:40.823156+00:00: independently admitted 9385013624094020582_2547_650_2567_650; live Insula reconciled 16 workers, 30 retained files, 3 verified evictions; {'records': 1980, 'points': 36064438, 'identity_array_digest': '5a6fe52aba09d19f7e688542d102a453bf9ae08ee7352fadd3deb39b281e5151', 'status': 'all returned arrays independently match verified source point records'}. Original 103-scene cohort unchanged; scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 1191788760630624072_3880_000_3900_000: 4730880 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

2026-10-01T01:57:04.083564+00:00: independently admitted 1191788760630624072_3880_000_3900_000; live Insula reconciled 16 workers, 30 retained files, 3 verified evictions; {'records': 1990, 'points': 35405780, 'identity_array_digest': 'c5eb0b9c1b5e0bdeaa22d9501b4bb0467907a618055219bb7fea5719319cda76', 'status': 'all returned arrays independently match verified source point records'}. Original 103-scene cohort unchanged; scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 6390847454531723238_6000_000_6020_000: 4666869 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

2026-10-01T02:08:14.468354+00:00: independently admitted 6390847454531723238_6000_000_6020_000; live Insula reconciled 16 workers, 30 retained files, 3 verified evictions; {'records': 1990, 'points': 34795683, 'identity_array_digest': 'fce69710593391a4f6f49a41259542e38d964bc1d5b5643506d1cde81ceba5f9', 'status': 'all returned arrays independently match verified source point records'}. Original 103-scene cohort unchanged; scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 13840133134545942567_1060_000_1080_000: 2848469 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

2026-10-01T02:21:04.859417+00:00: independently admitted 13840133134545942567_1060_000_1080_000; live Insula reconciled 16 workers, 30 retained files, 3 verified evictions; {'records': 1980, 'points': 31936558, 'identity_array_digest': 'eba51f49a471582aa61e64f976d405b9529369edb1f947269a46d08dec017670', 'status': 'all returned arrays independently match verified source point records'}. Original 103-scene cohort unchanged; scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 5525943706123287091_4100_000_4120_000: 4620109 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

2026-10-01T02:31:56.064715+00:00: independently admitted 5525943706123287091_4100_000_4120_000; live Insula reconciled 16 workers, 30 retained files, 3 verified evictions; {'records': 1990, 'points': 34015823, 'identity_array_digest': 'a479103c1c44f4f5500cad27b9de9fba669a280e6ad117891b6ab307455e63b2', 'status': 'all returned arrays independently match verified source point records'}. Original 103-scene cohort unchanged; scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 5200186706748209867_80_000_100_000: 2351147 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-10-01T02:43:15.084842+00:00: Independently admitted scene `5200186706748209867_80_000_100_000`: 1,990 point records, 26,731,204 points; live Insula verified 30 retained files, 16 worker receipts and three evictions. Cohort now 62/103, 2,116,015,978 points; 60 camera scenes. Protocol and scientific comparisons remain open. Evidence: `cohort-checkpoint-5200186706748209867_80_000_100_000-verified.json`.

Read-only native scientific semantic support pilot passed for 15696964848687303249_4615_200_4635_200: 4833493 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-10-01T02:47:14.621816+00:00: Added independently checked live semantic receipt for `15696964848687303249_4615_200_4635_200` (4,833,493 eligible native labels); aggregate 42/103 scenes and 183,601,765 eligible labels. Source admission, reconstruction/report identity, consumer/orchestrator hashes and receipt artifacts checked. Full lifecycle linkage pending; live checkpoint observer running, queue driver PID 1609839 confirmed alive. Full cohort and scientific comparisons remain open.

- 2026-10-01T02:52:26.725463+00:00: Independently admitted `15696964848687303249_4615_200_4635_200`: 1,980 records, 35,108,184 points; live checkpoint 30 retained files/16 workers/3 evictions. Cohort 63/103, 2,151,124,162 points, 61 camera scenes. Linked 4,833,493 native semantic labels to verified reconstruction/publication; 42 observed semantic scenes linked. Full cohort/protocol/models remain open.

Read-only native scientific semantic support pilot passed for 10599748131695282446_1380_000_1400_000: 2926541 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-10-01T02:57:21.941222+00:00: Independently checked semantic capture `10599748131695282446_1380_000_1400_000`: 2,926,541 native eligible labels; source/reconstruction/report/runtime-artifact and current consumer/orchestrator identities reconciled. Coverage 43/103 with 186,528,306 eligible labels; lifecycle linkage pending independent checkpoint. No scientific comparison claim.

- 2026-10-01T02:59:30.657793+00:00: Expanded resource inventory independently ran live in locked offline CPU Insula, 59 comparable completed lifecycles; median 612.281s, max 762.418s, measured sum 36205.072s. Four manual/recovery exclusions explicit; no extrapolation, scientific budget adoption or gate closure. Evidence `scientific-preprocessing-resource-expanded-verified.json`.

- 2026-10-01T03:06:32.864558+00:00: Independently admitted `10599748131695282446_1380_000_1400_000`: 1,980 records, 32,911,565 points; live checkpoint 30 retained files/16 workers/3 evictions. Cohort 64/103, 2,184,035,727 points, 62 camera scenes. Linked 2,926,541 native semantic labels to verified reconstruction/publication; 43 observed semantic scenes linked. Full cohort/protocol/models remain open.

Read-only native scientific semantic support pilot passed for 4575961016807404107_880_000_900_000: 4903102 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-10-01T03:16:17.145267+00:00: Sequential independent admission `4575961016807404107_880_000_900_000`: fresh live Insula 30 retained files/16 workers/3 evictions, all17 source/runtime/current checker identities reconciled. 1,980 records/35,944,040 points; cohort 65/103 and 63 camera scenes. Linked 4,903,102 native semantic labels; coverage 44/103. Scientific protocol/models/comparisons remain open. Evidence `cohort-checkpoint-4575961016807404107_880_000_900_000-verified.json`.

- 2026-10-01T03:19:03.576324+00:00: Training-box decoded-source adapter preparation: expected missing-module RED recorded before implementation, then13 targeted live groups passed including real fixture Parquet streaming and explicit TensorFlow absence. Independent literal quantiles preserve native center-Z distinct from height; omitted/extra/duplicate/non-training/truncated/malformed sources refuse aggregate completion. Current candidate/test/log/runtime receipt pins verified. Actual64 payload replay and separate live quantile consumer remain open; no protocol adoption. Evidence `training-box-sources-parquet-verified.json`.

Read-only native scientific semantic support pilot passed for 10082223140073588526_6140_000_6160_000: 5094095 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-10-01T03:27:34.549036+00:00: Sequential independent admission `10082223140073588526_6140_000_6160_000`: fresh live Insula 30 retained files/16 workers/3 evictions, all17 source/runtime/current checker identities reconciled. 1,970 records/37,307,825 points; cohort 66/103 and 64 camera scenes. Linked 5,094,095 native semantic labels; coverage 45/103. Scientific protocol/models/comparisons remain open. Evidence `cohort-checkpoint-10082223140073588526_6140_000_6160_000-verified.json`.

- 2026-10-01T03:28:32.659013+00:00: Independent training-box reference consumer: expected missing-module live RED recorded before implementation;23 targeted live fixture groups pass, including separate producer/reference Parquet reopens and standalone import independence. Standard-library native parsing/accounting/sorted quantiles, literal boundary faults, absent classes and interrupted reads checked. Candidate/runtime/log receipt identities verified. Actual64-source independent distributions/resource measurements and scientific freeze remain open. Evidence `training-box-reference-parquet-verified.json`.

Read-only native scientific semantic support pilot passed for 3657581213864582252_340_000_360_000: 5148261 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-10-01T03:40:31.751953+00:00: Sequential independent admission `3657581213864582252_340_000_360_000`: fresh live Insula 30 retained files/16 workers/3 evictions, all17 source/runtime/current checker identities reconciled. 1,980 records/37,501,560 points; cohort 67/103 and 65 camera scenes. Linked 5,148,261 native semantic labels; coverage 46/103. Scientific protocol/models/comparisons remain open. Evidence `cohort-checkpoint-3657581213864582252_340_000_360_000-verified.json`.

- 2026-10-01T03:43:22.557437+00:00: Bounded training-source wire preparation: missing reader observed live before implementation;32 targeted live groups now pass, including verified producer/reference wire passes, SHA256/MD5-specific faults, short reads, ambiguous/oversized headers, row/schema faults, empty sources, skipped consumption and completion/trailing-data failures. Current candidate/runtime/log receipt identities checked. Ruling: streamed stdin/consumed acknowledgements preserve one-source disk staging for the planned64-source aggregate; a faulty handshake or memory bound prohibits real replay acceptance. Actual full-source client/process orchestration remains open. Evidence `training-box-wire-integration-verified.json`.

Read-only native scientific semantic support pilot passed for 5468483805452515080_4540_000_4560_000: 3871771 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-10-01T03:48:58.521010+00:00: Sequential independent admission `5468483805452515080_4540_000_4560_000`: fresh live Insula 30 retained files/16 workers/3 evictions, all17 source/runtime/current checker identities reconciled. 1,710 records/26,564,493 points; cohort 68/103 and 66 camera scenes. Linked 3,871,771 native semantic labels; coverage 47/103. Scientific protocol/models/comparisons remain open. Evidence `cohort-checkpoint-5468483805452515080_4540_000_4560_000-verified.json`.

Read-only native scientific semantic support pilot passed for 4427374597960783085_4168_000_4188_000: 5025174 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-10-01T04:01:25.340850+00:00: Sequential independent admission `4427374597960783085_4168_000_4188_000`: fresh live Insula 30 retained files/16 workers/3 evictions, all17 source/runtime/current checker identities reconciled. 1,990 records/36,641,562 points; cohort 69/103 and 67 camera scenes. Linked 5,025,174 native semantic labels; coverage 48/103. Scientific protocol/models/comparisons remain open. Evidence `cohort-checkpoint-4427374597960783085_4168_000_4188_000-verified.json`.

Read-only native scientific semantic support pilot passed for 183829460855609442_430_000_450_000: 4501107 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-10-01T04:11:42.678484+00:00: Sequential independent admission `183829460855609442_430_000_450_000`: fresh live Insula 30 retained files/16 workers/3 evictions, all17 source/runtime/current checker identities reconciled. 1,990 records/33,603,771 points; cohort 70/103 and 68 camera scenes. Linked 4,501,107 native semantic labels; coverage 49/103. Scientific protocol/models/comparisons remain open. Evidence `cohort-checkpoint-183829460855609442_430_000_450_000-verified.json`.

Read-only native scientific semantic support pilot passed for 3437741670889149170_1411_550_1431_550: 6850317 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

- 2026-10-01T04:27:18.639428+00:00: Sequential independent admission `3437741670889149170_1411_550_1431_550`: fresh live Insula 30 retained files/16 workers/3 evictions, all17 source/runtime/current checker identities reconciled. 1,980 records/35,636,742 points; cohort 71/103 and 69 camera scenes. Linked 6,850,317 native semantic labels; coverage 50/103. Scientific protocol/models/comparisons remain open. Evidence `cohort-checkpoint-3437741670889149170_1411_550_1431_550-verified.json`.

Read-only native scientific semantic support pilot passed for 18295766828140813622_6775_000_6795_000: 3255453 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 14262448332225315249_1280_000_1300_000: 4660924 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 18446264979321894359_3700_000_3720_000: 3004292 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 14687328292438466674_892_000_912_000: 4686314 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 6161542573106757148_585_030_605_030: 3459789 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 6183008573786657189_5414_000_5434_000: 4944961 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 15611747084548773814_3740_000_3760_000: 3267211 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 30779396576054160_1880_000_1900_000: 4804034 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 1457696187335927618_595_027_615_027: 5549588 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 17962792089966876718_2210_933_2230_933: 4452916 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 18331704533904883545_1560_000_1580_000: 4938109 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 17626999143001784258_2760_000_2780_000: 4481319 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 7650923902987369309_2380_000_2400_000: 3272997 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 1071392229495085036_1844_790_1864_790: 6664082 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 8956556778987472864_3404_790_3424_790: 4277335 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 15959580576639476066_5087_580_5107_580: 5031192 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 447576862407975570_4360_000_4380_000: 4619688 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 1024360143612057520_3580_000_3600_000: 4391080 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 11048712972908676520_545_000_565_000: 4357367 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 9243656068381062947_1297_428_1317_428: 9774875 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 14081240615915270380_4399_000_4419_000: 3191118 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 933621182106051783_4160_000_4180_000: 4660723 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 12831741023324393102_2673_230_2693_230: 6886353 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 6680764940003341232_2260_000_2280_000: 5296384 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 18024188333634186656_1566_600_1586_600: 3127216 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 8331804655557290264_4351_740_4371_740: 6171739 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 2094681306939952000_2972_300_2992_300: 3725833 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

Read-only native scientific semantic support pilot passed for 4575389405178805994_4900_000_4920_000: 4713363 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

2026-10-01: Fourth storage recovery publication verified terminal exit 0; all six live stages passed, all 12 retained artifacts and three candidate code hashes rechecked. Complete 45,641-member canonical stream (7,182,551,040 bytes) mirrored as 491,722,411-byte gzip archive; measured end 9,473,165,411 bytes below unchanged 16,106,127,360-byte cap. Evidence: research/sidecar-fourth-publication-retained-audit.json. Compressed-aware eviction, camera lifecycle and admission remain open; no training or held-out claims.

2026-10-01: Added separate compressed_sidecar_eviction module, preserving original pinned eviction. Live Insula RED missing module then GREEN five controlled cases: format/expanded identity/capacity/payload refusals and verified deletion. Evidence research/compressed-sidecar-eviction-live-verified.json. Actual scene eviction remains required.

2026-10-01: Actual scene 4575389405178805994_4900_000_4920_000 compressed sidecar eviction passed live Insula after queue lease, independent retained publication/code/runtime rehash and metadata capacity check. Released 7629039187 bytes; ending aggregate 1854553663 bytes. Evidence research/interrupted-sidecar-eviction-fourth-verified.json. Camera lifecycle started via .scratch/resume-interrupted-camera-fourth.py; admission remains open.

2026-10-01: Fourth recovery camera preprocessing/publication/independent replay/eviction all passed. Actual 30 retained artifacts, 16 worker receipts and three verified evictions independently admitted live by unchanged cohort_checkpoint verifier. Scene 4575389405178805994_4900_000_4920_000 raises original cohort admission to 100/103; 22 missing semantic captures remain explicit. Evidence research/cohort-checkpoint-4575389405178805994_4900_000_4920_000-verified.json. Remaining three scenes and scientific comparisons stay open.

2026-10-01: Original queue resumed for final three scenes under existing leases, PID 1241409. Previous queue and four observers verified terminal before restart. Fresh independent admission/capture/box/semantic recovery continuations recorded in research/downstream-after-fourth-recovery-pending.json; existing source cohorts and 22-archive recovery inventory retained. No duplicate capture or aggregate writers launched.

2026-10-01: While final three scene queue confirmed live, rehashed all103 native-shape jobs and original source receipts, exact memberships/key inventories, 203850 return records and 17382154779 serial source bytes. Host preparation evidence research/native-shape-pre-execution-input-audit.json; no shape HDFS payload replay or range-grid gate claim.

2026-10-01: Unchanged compressed archive validator independently exercised live on canonical valid archive and missing/duplicate/undeclared/unsafe native member mutations. Recomputed outer and expanded hashes for each mutation so structural refusal, not digest mismatch, is proved. Evidence research/compressed-component-member-inventory-live-verified.json. Final-three original queue confirmed live during verification.

Read-only native scientific semantic support pilot passed for 7119831293178745002_1094_720_1114_720: 4964606 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

2026-10-01: Final-three scene7119831293178745002_1094_720_1114_720 native reconstruction completed and live semantic capture retained4964606 eligible labels. Receipt/artifacts/current candidate hashes and native reconstruction/report identities independently rechecked; retained-audit JSON recorded. Queue1241409 remains live; independent lifecycle admission pending.

2026-10-01: Scene7119831293178745002_1094_720_1114_720 full point/sidecar/camera lifecycle completed. Independent live admission proves30 retained files,16 worker receipts,3 verified evictions; admission receipt/artifacts rehashed. Original cohort now101/103; queue1241409 confirmed live preprocessing5372281728627437618_2005_000_2025_000. Missing22 semantic recovery inputs unchanged. Scientific model comparisons remain open.

Read-only native scientific semantic support pilot passed for 5372281728627437618_2005_000_2025_000: 5769701 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

2026-10-01: Scene5372281728627437618_2005_000_2025_000 native reconstruction/live semantic capture completed with5769701 eligible labels. Retained receipt/artifacts/current candidates and reconstruction/report pins rehashed; retained-audit JSON saved. Full lifecycle not yet admitted.

2026-10-01: Scene5372281728627437618_2005_000_2025_000 completed entire point/sidecar/camera lifecycle and independent live admission:30 retained files,16 worker receipts,3 verified evictions. Admission receipt/artifacts rehashed; original cohort102/103. HDFS upload timeout recovered via original Waystone retry, preserving owned queue. Last original scene13982731384839979987_1680_000_1700_000 preprocessing live. Scientific comparisons remain open.

Read-only native scientific semantic support pilot passed for 13982731384839979987_1680_000_1700_000: 4874517 eligible valid-range labels; independent literal class-count loop agrees with semantic_support. No source mutation/staging/driver edits. Final lifecycle linkage/full-cohort support and protocol remain open.

2026-10-01: Final original scene13982731384839979987_1680_000_1700_000 reconstruction and live semantic capture passed;4874517 eligible labels independently retained-rehashed with source reconstruction/report and candidate identities. Point publication live; full lifecycle still pending.

2026-10-01: Final original scene compressed publication all six live stages verified and all27983-member identities retained-rehashed; actual compressed eviction passed live, released7483004220 bytes, ending aggregate1900581504 bytes below unchanged cap. Camera lifecycle started via .scratch/resume-interrupted-camera-fifth.py; checkpoint/full scientific admission still open.

2026-10-01: Final original scene13982731384839979987_1680_000_1700_000 camera lifecycle all four live stages passed, followed by unchanged independent cohort_checkpoint admission:30 retained files,16 worker receipts,3 verified evictions. Full original103 scene point lifecycle admitted;22 missing semantic captures remain explicit. This closes processing admission only, not scientific data/protocol or model comparisons.

2026-10-01: Reconciled original pilot camera coverage:100 full checkpoints plus separate15036582848618865396_3752_830_3772_830 camera publication/replay/eviction evidence, rehashed. Two explicit missing camera lifecycles1730266523558914470_305_260_325_260 and4759225533437988401_800_000_820_000. Evidence research/camera-lifecycle-coverage-reconciled-host-audit.json.103 point admission does not imply103 camera completion.

2026-10-01: Real64 box producer/reference HDFS replay completed exit0 and separate live retained receipt audit admitted726715 native rows. Evidence research/training-box-full64-replay-verified.json; descriptive training-only summary saved. Cyclist support5030 box rows but38 unique tracks; row count must not imply independent trial count. No anchor adopted or scientific quality claim. Semantic recovery awaiting bounded capture PID1773243 and wrapper1241412 terminal.

2026-10-01: Original semantic recovery completed first archive producer but admission wrapper refused overlapping source/output mounts. Preserved first immutable receipt and failed empty audit directories; separate wrapper v2 places live audit outputs under cache/insula outside source. Unchanged independent semantic_recovery_receipt verifier admitted first original missing scene1730266523558914470_305_260_325_260. Serial continuation2057684 retains full22 inventory and code pins; no pipeline modifications or sources restarted.

2026-10-01: Revalidated v2 semantic recovery terminal failure; proven exact unaligned RLIMIT versus native4096-byte O_DIRECT final write. Added versioned aligned staging and independent receipt verifier without modifying previously admitted modules. Fail-first tests reproduced native EINVAL and missing padding reservation; live offline Insula passed11 relevant tests including aligned positive cases, rehashed padding/bound/contract mutants and old receipt compatibility. Started full22 recovery v3 PID2230074, retaining existing first scene and immutable inventory49767cc6c0d1a3d309e025ea563c4f1fa88883846d2664d76838e12de2810a80. Actual aligned HDFS success/full coverage remain unproven.

2026-10-01: Formerly failing original4759225533437988401_800_000_820_000 now recovered and independently live-admitted under aligned transfer contract. Exact3251701760-byte/SHA archive accepted; explicit2048-byte padding/3251703808 child limit and transient aggregate bound preserve unchanged15GiB cap. Retained worker/receipt/audit artifacts and current code rehashed in semantic-aligned-real-recovery-retained-audit.json. Recovery2/22; continuation2230074 confirmed live for remaining20. No model/protocol completion claim.

2026-10-01: Prepared full103 native shape execution with an independently live-tested retained receipt auditor (positive real engineering replay and11 rehashed mutations refused). Complete103 jobs/source manifests rehashed;203850 expected return records preserved. Armed continuation PID2300693, waiting on authoritatively live semantic2230074 and exact22 admissions. Existing pipeline code pins unchanged; no parallel competing source staging. First audit launch failed on RO-root mountpoint creation; corrected to /tmp/auditor under private tmpfs, failed log preserved, live2-group tests then passed. Real shape replay, full reconciliation and point-grid linkage remain pending.

2026-10-01: Independent camera-only retained checkpoint pilot passed live: existing15036582848618865396_3752_830_3772_830 reconciles five workers and one eviction; rehashed source/manifest mutants refused. Prepared and preflighted exact two-camera-gap continuation, now armed PID2371235 after full shape replay. While preparing it, semantic2230074 and shape2300693 were authoritatively terminal: seventh semantic receipt refused +71 bytes staging observation. The waiting shape log first line is71 bytes and was written into working root outside queue ownership. Preserved failed receipt/output and refusal log; no weakening of receipt equality or scientific gate. Moved all new continuation logs outside working to cache/insula/continuation-logs. Semantic v4 PID2348064 re-audits six retained admissions and uses new accounted output root for remaining16, avoiding overwriting refused seventh. Shape v2 PID2350750 retains original103 jobs and waits on new semantic owner. Pipeline code unchanged; scientific comparisons remain open.

2026-10-01: Original seventh scene3375636961848927657_1942_000_1962_000 recovered to fresh output and independently live-admitted by unchanged aligned receipt verifier. Strict working-before plus exact archive equality now holds; all retained worker/receipt/audit artifacts and current code rehashed. Recovery7/22. New semantic2348064, shape2350750 wait, and camera-gap2371235 wait confirmed live; refused prior receipt retained unadmitted.

2026-10-01: Added streaming point/native-grid linkage checker outside pinned pipeline modules. Live fixtures reject missing/extra/duplicate keys, null shape for present return, invalid/duplicate pixels and preserve empty-border/missing/present-empty support. Complete native engineering replay passes3970 records/71891534points,15present-empty,9204259eligible semantics; measured70.972s/75736KiB worker peak. A separate live retained admission reconciles source report/cardinalities, original output, current helper/adapter hashes and resources. First native launch correctly failed on legacy engineering report without return_present; corrected legacy fixture boundary to explicit materialized artifact records, failed logs retained. Scientific103 linkage and comparisons remain open.

2026-10-01: Prepared all103 immutable scientific point/native-shape linkage input records, rehashing original point checkpoints/publication receipts/manifests/current candidates and source LiDAR identities. Exact203850returns/3513295187points retained; serial derived archive bytes327604899840. Candidate SHA393220a85c198d61eba135e95a5888997fd9ec50cae16ef50025ae16ff0d3233. New full-cohort linkage plan records true scope and required live/source/retained verifiers. Inventory is host preparation only; full scientific point-grid payload replay remains unarmed pending independently admitted native shapes and current serial owners.

2026-10-01: Full103 point/grid metadata admitted live with seven scope/source/job/publication mutations refused. Reusable source driver fixture passes two independent full live payload passes plus retained receipt admission; seven rehashed receipt mutants refused. First fixture launch correctly refused a symlink rootfs; preserved it and used explicit independently verified runtime root in a new fixture. Driver holds queue/raw exclusion, reserves16MiB consumer metadata under15GiB, preserves exact source identity and stage cleanup. Armed original103 linkage continuation PID2585329 behind current native shape and two-camera-gap owners, logging outside working. Semantic v4 authoritatively terminal after22/22 separate live admissions; original81+22 gives103 coverage, aggregate evidence reconciliation still open. Scientific models/protocol remain uncompleted.

2026-10-01: Independently live-reconciled all103 native semantic receipts:81 original captures plus22 recovered,478579462 eligible positive-range labeled points,3118annotated frames. Each source/report/runtime/current consumer/artifact identity and all23-bin frame histograms checked against full103 point inventory. Official/research splits retained64train/8development/16LiDARvalidation/16cameravalidation with original overlap; no joint437-frame narrowing. Snapshots include sealed receipt metadata only and are rehashed against authoritative originals before/after copy. First aggregate launch refused unsafe cache/output overlapping mounts before execution; corrected to disjoint bounded receipt-metadata snapshot source, preserved failed directory. Evidence research/scientific-semantic-full103-verified.json. Complete semantic support does not freeze protocol or establish model accuracy.

2026-10-01: Native shape continuation2350750 authoritatively terminal after all103 actual HDFS source replays, each producer, independent source reread and independent retained live receipt admission. Full-set host audit rehashes all individual receipts/artifacts/audit files against original jobs and membership:203850records,203850present shapes,0null shapes. Scientific point-grid linking not inferred from dimensions. Camera-gap2371235 confirmed live preprocessing first gap; point-grid2585329 confirmed live waiting for exact upstream completion.

2026-10-01: Both missing original camera lifecycles completed and separately live checkpoint-admitted (each five workers, one verified eviction); current retained checkpoint/audit hashes rechecked. All103 camera lifecycle records now exist, full original+pilot+gap aggregate audit remains distinct. Full scientific point-grid continuation2585329 progressed to real original scene1730266523558914470_305_260_325_260:1970returns/32547972points/2720971eligible semantics agree with independent full reference and a third live receipt audit. All retained producer/reference/audit files rehashed. Full103 point-grid progression is active, not complete; models/protocol remain open.

2026-10-01: Separate live full103 camera aggregate admission completed against original manifest, all17 source hashes per scene, runtime/current candidates, every retained lifecycle artifact and verified eviction lineage. Reconciled100 full checkpoints plus1 separately preserved pilot plus2 recovered gaps; each native camera replay reopened explicitly and exact scope enforced. Evidence scientific-camera-full103-verified.json, output/support hashes retained-rechecked. Native camera totals{'camera_image': 101925, 'camera_segmentation': 13675, 'camera_box': 974983}, eligible annotated camera pixels29254724875. This closes original camera lifecycle coverage only; class mapping/predicted model quality/rolling projection and scientific protocol remain separate. Original processing progress file left unchanged because an earlier point-grid inventory hashes it.

### 2026-10-01T13:27:30.984397+00:00 — task evidence reconciliation

Updated ticket07 and the task index to distinguish completed full64 box, full103 semantic/native-shape/camera gates from active point/grid replay and open scientific freeze. Confirmed PID2585329 live at01:20:58; progress39/103,77,270 returns,1,328,979,299 points. No pinned pipeline/worker files changed; no ticket closure or scientific outcome claimed.

### 2026-10-01T13:29:22.237773+00:00 — training-only anchor derivation

Derived eight full64 median LWH/native-center-Z templates without validation outcomes. Fresh rootfs identity check and live TF-free Insula verifier passed exact candidate/summary/audit hashes, all four classes, paired yaw and independent analytic non-square grid ordering. Retained output/log rehashed. Candidate preparation only; no optimizer updates or ticket closure. Pipeline modules and active point/grid pins unchanged.

### 2026-10-01T13:32:46.702051+00:00 — optimizer-inclusive resource fixture

Fresh GPU root identity and driver hashes checked; synthetic full-model three-step Adam fixture passed with eight anchors and all four classes. Peak allocated1,417,361,920B. Separate fresh CPU Insula retained auditor checked exact code/artifact identity, parameter count and optimizer state bytes; retained audit artifacts rehashed. Scientific dataset updates remain zero. Added only GPU/scratch preparation workers; no active pipeline pins changed.

### 2026-10-01T13:37:42.414153+00:00 — numerical detection protocol candidate

Created source/code-pinned PointPillars protocol candidate with explicit training, ROI/sampling, overfit, metrics, uncertainty and resource limits; preserves full native held-out GT. Fresh live CPU Insula structural audit and six leakage/feature/denominator/resource mutations passed; retained artifacts rehashed. Preparation only: native feasibility and scientific protocol admission still open. Confirmed point/grid PID2585329 live at01:27:28 with42/103 scenes. No pipeline pins changed.

### 2026-10-01T13:41:34.757699+00:00 — native training-only overfit selection

Pinned exactly16 overfit frame identities from12,676 unique native frame keys across64 training scenes. Fresh live CPU Insula independently reopened source-linked shape receipts/artifacts, required all ten returns per frame and reconstructed global hash order; four selection mutations refused. Retained verifier artifacts rehashed. Native point/box joins and overfit are still open. Confirmed PID2585329 live at01:32:32 with45/103 grid replay admissions. No active pipeline/worker pins changed.

### 2026-10-01T13:49:56.318907+00:00 — native overfit target worker and queued extraction

Live red/green source-target tests and separate streamed Parquet producer/literal-reference fixture passed; retained fixture artifacts rehashed. Queued one-shot PID3645336 for13 real native lidar_box sources covering16 fixed training frames. It waits for pinned point/grid owner2585329 terminal plus all103 admissions before staging; acquisition under original queue/raw caps, three live checks per source. Pending execution is not scientific acceptance. No pipeline pins changed.

### 2026-10-01T13:59:00.296596+00:00 — selected native physical-frame extraction preparation

Live red/green frame assembly and complete archive producer/literal-reference fixture passed; retained output hashes rechecked. Queued PID3736668 behind box owner3645336 for13 immutable training publications/16 selected frames;42,230,835,200 serial I/O bytes,1GiB selected-payload cap within unchanged15GiB working cap. Independent retained audits will join native boxes by frame and report unknown/zero-point/outside-ROI exclusions. Queued is not actual native admission. Active pipeline and worker pins unchanged.

### 2026-10-01T14:12:27.700988+00:00 — native target-assignment preparation

Live red/green target assembly tests passed. Two full524,288-anchor synthetic fixtures independently compared literal overlap, assignment, center-Z/log-dimension/yaw residual and direction equations; v2 adds negative and2pi-equivalent headings. All four synthetic classes have positive anchors; zero-overlap GT is explicitly reported uncovered. Artifacts rehashed and geometry-module identities reconciled to immutable protocol pins. Actual native support/cost and optimizer/overfit remain unverified. No active pipeline or worker pins changed.

### 2026-10-01T14:54:01.877667+00:00 — cache integration and verified yaw boundary correction

Integrated live physical packing/lineage and target reference checks passed. Valid all-background ROI accepted, uncovered eligible target retained, unresolved annotation coverage refused. A live regression proved old scratch target helper encoded +pi with a canonical negative direction bin and decoded it as0; additive v2 helper canonicalizes GT before residual encoding and bins. Exact +/-pi,+/-2pi roundtrip, four target groups and v3 integrated/edge fixtures pass with separate literal audits. Earlier code/evidence preserved. All retained artifacts rehashed; no active pipeline or queued worker pins changed. Native data/overfit and scientific comparisons remain open.

### 2026-10-01T14:55:57.394325+00:00 — replayable yaw correction receipt

Replayed corrected heading targets in freshly identity-verified CPU Insula with exact code/test/decoder digest assertions and UTC/command receipt. Separate live retained checker confirms log, six boundary headings/two anchor orientations and current code hashes; artifacts rehashed. Existing failure/pass evidence preserved. No active pipeline or queued worker pins changed; native acquisitions remain pending and no optimizer updates claimed.

### 2026-10-01T15:23:36.110118+00:00 — native cache preparation queued

Live reusable literal checker passed positive/background/uncovered cache fixtures, with complete524,288-anchor equations checked in bounded chunks. Queued PID350971 behind selected-point owner3736668 for exactly16 training-only frame caches using corrected yaw helper. Fixed tiny-overfit PCG64 seeds,1.25GiB prepared-payload cap within15GiB working storage and16GiB worker address-space cap; no optimizer run authorized by this preparation. Fixture artifacts rehashed; active pipeline and existing queued worker pins unchanged.

### 2026-10-01T15:47:08.467880+00:00 — full103 grid and fixed native box closure

Original grid owner terminated after103 independent source admissions. Reopened and rehashed every point/grid receipt, producer/reference artifact, current pipeline digest and retained third-live-audit artifact; reconciled203,850 records,3,513,295,187 points and478,579,462 eligible semantic labels. Native box owner terminated after13 admitted source extractions; all retained source/audit artifacts rehashed. Selected native-point extraction remains live; native cache owner350971 waits behind it. Overall scientific goal remains open.

### 2026-10-01T15:56:29.055647+00:00 — native16-frame cache completion

Selected-point owner terminated after all13 scenes admitted; native cache owner terminated after all16 fixed frames independently admitted. Reopened every cache producer receipt, output artifact and independent live checker artifact. Aggregate input/retained points 2834683/1698387, eligible/uncovered native targets 750/19. Preparation is complete; GPU optimizer/overfit/scientific comparisons remain unproven.

### 2026-10-01T16:06:09.501688+00:00 — native optimizer pilot independently admitted

Live single-B200 pilot completed16 diagnostic updates on the fixed training caches, with finite gradients/parameters, clip10 and exact model-output/Adam-state checkpoint restoration. Separate live retained audit rehashed inputs and code, reconciled native positive-anchor support, loss arithmetic and all16 Adam step counters. Peak allocated GPU bytes 1415641088, reserved 2543845376, RSS KiB 2130284; measured worker time 3.290938s including native I/O and checkpoint checks. This is a short diagnostic, not an overfit result or main-study budget estimate. Pilot-v1 mount failure and pilot-v2 scalar-device restoration failure are preserved; v2 performed16 failed-admission diagnostic updates, v3 performed16 accepted updates. Total executed native diagnostic updates32; none used for heldout claims. Tiny-overfit native scoring/export and protocol admission remain open.

### 2026-10-01T20:50:10.955993+00:00 — fixed16 training audit and failed native score; architecture discussion

Completed2000 updates from fresh seed17. Separate live checkpoint replay checked all16 exact final heads, literal initial/final losses and Adam steps. Loss decreased2995.379291534424 to1.9208379872143269. Native scorer produced mean LEVEL2 APH.0056932515 below.8; independent geometry/export/scoring audit remains pending, so no overfit admission. Observational live head diagnostics reported432 positive-anchor-origin proposals among8000 exports and49,723 background anchors above.05; anchor counts are not object recall. Ask-matt source research and discussion draft captured architecture, declared deviations and diagnostic tasks D1–D7; no new model recipe adopted or trained. Overall goal remains active.

### 2026-10-01T21:19:07.358776+00:00 — one-batch native overfit independently checked

First fixed training key, seed17,2000 updates with existing4.85M PointPillars adaptation and unchanged optimizer. Evaluation loss5954.59423828125 to.05814296752214432. Native LEVEL2 APH vehicle.998079 (3 GT), pedestrian.988051 (3 GT), sign.226459 (11 GT); no cyclist GT. Mean populated-class APH.7375296666666666 fails.8; all17 eligible boxes including uncovered targets retained. Separate live audits checked initial/final loss, checkpoint heads, literal decoding/NMS, original-point counts/NLZ, exact eligible GT, all protobuf fields and repeated native metrics. Source/artifact receipts rehashed after audit. Decision needs-more-evidence; model demonstrates vehicle/pedestrian memorization on this batch but full one-batch gate remains failed and full16 gate unchanged.

### 2026-10-01T21:54:50.689576+00:00 — Tier1 timing/quality curve and BN causal diagnostic

Tier1 batch memorization required for model architecture development, preceding tiny-cohort and heldout gates. Replayed2000 unchanged updates with11 preregistered checkpoints; final heads exactly match original. Independent live audits reconciled all saved losses/components/timing and independently decoded/suppressed predictions, recomputed measurement metadata, reread protobuf fields and reran every native score. Vehicle/pedestrian APH>=.8 first observed750, bracket(500,750], synchronized-step wall(38.006,53.718]s. Mean gate first observed1500, bracket(1000,1500],(72.922,107.302]s, then failed2000; per-class gate never passed. Initial negative focal accounts for99.91% of total. Zero-update frozen-weight BN refresh improved meanAPH.737530→.864156, confirmed separate literal BN moments/unchanged weights/exact heads and native audits; signs.595564 still fail per-class. Three signs lack positive anchors and some thin boxes require centimetre precision. Decision needs-more-evidence; no whole-model adoption, no heldout claim. Curve resources:146.448s synchronized-step wall,152.134s worker,215.302s native score wall,327 clipped updates; do not equate iterations or loss threshold to time-to-native-fit. All receipts/artifacts rehashed.

### 2026-10-01T22:57:22.340836+00:00 — normalization-only matched treatments started

User authorized norm comparisons. Preregistered originalBN reference versus GN8BEV/originalPFNBN, GN8BEV/per-pointLN, and no norm, same first batch/seed17/2000-update/grid/loss/scorer. Live red→green contracts preserve convolution initialization and verify norm statistical axes/mode consistency. Serial GPU training controller is live; no main-scientific adoption. Referencepipeline unchanged. Independent loss audit v1 emitted a legacy stdout equality phrase despite deliberately removing reference-BN-head comparison for differing architectures; report itself correctly marked checkpoint replay separate. Preserved that record and ran corrected v2; separate native norm checkpoint replay remains required.

## Completed matched normalization investigation

[Audited comparison](normalization-ablation-results.md) reports11 checkpoints per treatment, independent live Insula scoring/audits and retained recipe/source evidence. GN backbone final meanAPH.878552; GN+point-LN.856792, with earlier sampled mean pass; originalBN.737530. No-norm primary decoder failure is retained; separately versioned score-first decoder is exactly equivalent on all33 normalized exports and admits independently audited no-norm meanAPH.621318. Every variant still fails sign per-class≥.8; fixture has no cyclists. Candidates only, no main-study adoption or ticket closure.

## Architecture study execution2026-10-02

User explicitly requested specification and execution. Written study/plan and tickets28–32 preserve main gates. Native contracts REDmissingmodule→GREEN pass; firstcohort serialGPU begun. Retain64 native-cache producer and separate literal source/allanchor audit pass; baseline targetNPZbyteidentity confirmed. Preflight: candidatefactory and forward/output contracts identical in train/replay; regenerated retention observations handled separately. No baselinepipeline mutations or incidental unrelated commits.

Architecture scheduler finding: initialfollowthrough tested residual_bev membership in serialized progress containing planned list, so it ran after deepPFN only. Context audit attempted before receipt and failedFileNotFoundError (no model mismatch); deepcheckpoint GPUreplay may overlap contexttraining. Corrected predicate reads trained list, preserved failedlog, ran fresh context exclusivev2 for uncontaminated timing and requested independent all11head/all2000loss/gradient trajectory equivalence. Baseline and primary receipts retained; only exclusivecontext step timing admitted for comparison.

Added written window/controlfollowup spec: maskedPFNcontrol,coarse8×8windowattention4heads and equalparameter coarseMLP. Missingmodule liveRED observed; GREEN and serial native runs queued behindretain64checkpointreceipt. This is parameter-matched rather than FLOP-matched.

Architecture independent code review: no critical model-mask/residual/window-partition defect. Important harness findings fixed: complete mapped residual weight coverage (live missinghelperRED→GREEN and intentional corrupt branch rejected), checkpoint artifact/source/driver/input/observation pins before+after plus checkpointmanifest/Adamshape/hyperparameter checks, and CPUscore/cache scientific-cap guards. Separate live actual-function fixture rejects corrupted artifact/source/driver/manifest/observation and capoverflow with retained failure record. Strong checkpoint admissions rerun; historical weak receipts retained. Masked point permutation gate added as required by spec; final report computes firstsustained sampled pass. These scientific-verifier issues are fixed rather than waived.

Evidence-driven extension: all_pillars control lifts fixture pillarcap20k→30k (all26384eligiblepillars), keeps32point cap and sameGNbaseline. New cache producer+independent source/allanchor audit and targetNPZbyteidentity pass. Separate spec records RNG sampling difference; run scheduled after strictGPUreplay readmission. It addresses observed3signobjects with all source-support cells discarded; does not repair unassignedtargets or establish heldout benefit.

## Architecture first cohort admitted

All8variants have live native2000update execution, independent loss checks, strict initial/final head/Adam replay and all11checkpoint geometry/export/native metric audits (88total). Final1529artifacthash reconciliation passes. ResidualBEV meanAPH.907812 and maskedpool.886386 are candidates for broader evaluation; allsignperclassgates fail and cyclists absent. Windowattention/control are essentially baseline quality; retention recovers source measurements without improving fixedrecipe fitting. [Results](../../../experiments/waymo-perception/research/architecture-first-cohort-results.md) and machine-readable receipts preserve scheduler failure/exclusive repeat and reviewed verifier fixes. No fullclass/heldout adoption or overallgoal closure.
