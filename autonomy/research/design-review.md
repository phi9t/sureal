# Waymo perception design review

Date: 2026-09-29. Scope: research closeout for the proposed manifest and
introspection seam; no dataset acquisition or executable conversion was run.
Code sources below are pinned to
`99a4cb3ff07e2fe06c2ce73da001f850f628e45a`, matching the existing upstream note.
Website facts were checked on the review date. Recommendations are SUREAL
design choices, not upstream guarantees.

**User constraint:** no TensorFlow; tensor processing uses Torch and/or JAX.
The SDK observations below describe upstream dependencies, not an allowed
runtime. The initial reader uses PyArrow directly and excludes SDK imports.

## Recommended first boundary

Use v2.0.1 component Parquet files for a bounded, offline metadata and raw-range
summary probe. Implement this with a Parquet reader without importing the SDK.
Defer point-cloud generation, motion compensation, image projection and v1
TFRecord support to separate capabilities. A manifest can preserve geometry
without claiming to have reconstructed it.

The [v2 tutorial](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/tutorial/tutorial_v2.ipynb)
explicitly permits any Parquet reader without protobuf dependencies, and shows
component/context file paths and flattened columns. Its demonstrated Python
SDK imports TensorFlow, however. The format guarantee does not establish that
the SDK is TensorFlow-free. The tutorial describes compatibility with v1.4.2
for v2-supported components; it does not establish complete v1 feature parity.

The [LiDAR component source](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/v2/perception/lidar.py)
imports TensorFlow directly. Its range image stores flattened values and shape
for four channels: range, intensity, elongation and no-label-zone membership.
The per-pixel pose carries vehicle-to-global transformations; only the first
return stores the pose, and the second shares it.

**Implementation implication:** a small explicit column contract copied from
pinned schema sources avoids the SDK runtime constraints for the initial probe.
Choose and lock the actual Parquet-reader environment from local compatibility
evidence. Do not force Python 3.10/3.11 solely because the deferred SDK needs it.
Do not silently substitute TFRecord when a requested Parquet component is
missing; report that capability as unavailable.

## Correct the component grains before designing joins

The [key hierarchy](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/v2/perception/base.py)
distinguishes the following grains. Release and split must be added by the local
manifest namespace because they are not these component keys.

| Component role | Upstream key dimensions |
| --- | --- |
| vehicle pose | context, timestamp |
| camera calibration | context, camera |
| LiDAR calibration | context, laser |
| camera image | context, timestamp, camera |
| LiDAR/range pose | context, timestamp, laser |
| LiDAR box | context, timestamp, laser object ID |
| camera box/association | context, timestamp, camera, camera object ID |

LiDAR object labels belong to the entire 3D scene and deliberately omit
`laser_name`; assigning them to a TOP-only namespace would change their meaning.
Camera and LiDAR object IDs remain separate namespaces, connected only by an
explicit association.

The [context component source](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/v2/perception/context.py)
defines `StatsComponent` as **frame-grain**, even though weather/location look
like segment metadata. It also retains distortion coefficients and rolling
shutter direction in camera calibration, and optional nonuniform beam
inclinations in LiDAR calibration.

**Implementation implication:** maintain a registry of component keys and
required columns. Validate uniqueness before any join. Anchor scene/frame rows
in `vehicle_pose` for the default profile; assemble sensor and object collections
separately, and attach each collection once per frame. Use many-to-one joins
for calibration and left-preserving frame assembly. Compare observed keys to
the anchor and report orphan and missing rows. Avoid joining ungrouped cameras,
lasers and boxes on timestamp. Do not require a fixed 200 frames merely because
segments are nominally 20 seconds at 10 Hz.

## Geometry and time must remain explicit

The [official perception page](https://waymo.com/intl/es/open/data/perception/)
defines vehicle axes as +x forward, +y left and +z up. Camera +x points outward
along the lens and +z points up, so this is not the common optical +z-forward
frame. Sensor extrinsics map sensor coordinates to vehicle coordinates; vehicle
pose maps vehicle coordinates to the segment's global frame. The page describes
two returns and reports no-label-zone channel values as 1 inside and -1 outside.
It also explains that some camera/LiDAR associations are absent because of
occlusion or field-of-view differences.

The [frame proto](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/dataset.proto)
specifies row-major transforms, and warns that frame timestamp is the start of
the first TOP scan while the frame pose is roughly near the middle of the
frame. Native 3D labels use that frame vehicle pose. For camera labels, an
explicit labeled camera entry with zero boxes means labeled-empty; absent
entries do not have that interpretation. Segmentation coverage is sparse,
including unlabeled points in otherwise labeled frames.

The [camera image component](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/v2/perception/camera_image.py)
stores its own SDC pose and pose timestamp, global-frame linear/angular
velocity, exposure duration, trigger time and readout completion time. These
timestamps are separate from the integer-microsecond frame key.

The [label proto](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/label.proto)
defines upright boxes with zero pitch/roll, length along x, width along y and
height along z; heading is radians normalized to `[-pi, pi)`. It distinguishes
native LiDAR boxes from camera-synchronized boxes shifted for image capture and
rolling shutter. Those are separate label semantics.

**Implementation implication:** name transforms by direction
(`vehicle_from_camera`, `vehicle_from_lidar`, `world_from_vehicle`), retain
row-major layout and source timestamps with units, and preserve the original
camera pose metadata. Do not assert synchronized poses from equal frame keys.
Validate finite values, homogeneous transform shape, rotation orthogonality and
determinant within declared tolerances. Keep coordinate conversion out of the
first probe; a later adapter must explicitly rotate into SUREAL conventions.

## Range statistics are not reconstructed points

The [v2 conversion helper](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/v2/perception/utils/lidar_utils.py)
uses calibration inclinations, reverses row inclination order, applies sensor
extrinsics and optionally takes per-pixel pose plus frame pose. A supplied
per-pixel pose requires frame pose. The point-cloud helper filters on positive
range. These operations require more than reshaping the stored values.

**Implementation implication:** v1 of this experiment should report per-sensor,
per-return shape, finite and positive range counts, finite positive range
min/max and no-label-zone counts. Verify flattened length equals the product of
shape and the last dimension is four; retain null/absent-return state and define
zero-valid-range extrema as null. Treat unknown no-label-zone codes explicitly,
not as booleans. A positive-range cell count is a valid-return count, not a count
of unique scene points and not a Cartesian point cloud. Never attach an XYZ
bounding box to a raw-range summary.

A later motion-compensated point conversion profile must add `lidar_pose` to
its acquisition allowlist where required, and prove the conversion against the
upstream equations using Torch/JAX, analytic fixtures and permitted reference
vectors without executing the TensorFlow helper. The current orientation
allowlist omits `lidar_pose`; that is acceptable for range statistics but
insufficient as a promise of motion-compensated TOP point output.

## Label availability is a data contract

The [dataset overview](https://waymo.com/open/about/)
reports unequal segment coverage across camera boxes, LiDAR boxes,
segmentation and keypoints. It describes box correspondence for pedestrians and
cyclists, whereas older pinned proto comments are narrower. Do not infer
complete association coverage or generalize component availability to every
segment. The [official terms and challenge rules](https://waymo.com/open/terms/)
say training/validation labels are available but test ground truths are
withheld. This research records the split behavior; it does not accept terms
or authorize data redistribution.

**Implementation implication:** distinguish available-nonempty,
confirmed-available-empty, unavailable/not-staged, withheld and unknown, with
reason and evidence. Missing Parquet label rows alone may not distinguish
unlabeled from labeled-empty because the object table does not encode the v1
camera-label container. Keep that state unknown unless an authoritative
coverage contract resolves it. Classify an unreadable staged file as corrupt,
not as an optional modality missing. Test-split label absence must not fail an
otherwise valid sensor manifest or become a claim of zero objects.

## Evidence still needed at execution time

No authenticated bucket inventory, sample footer/schema, dataset bytes or SDK
runtime was inspected in this review. GCS split prefixes, per-component row
coverage, exact schemas, byte budgets and HDFS configuration remain execution
evidence gates. Preserve a schema fingerprint per staged file and fail with a
specific incompatibility report when required columns or physical types differ
from the pinned contract. Synthetic fixtures can prove this behavior before
access exists; they must never be reported as a real Waymo probe.

The implementation plan should separate offline fixture verification from
authorized acquisition and the real one-context probe. Defer HDFS mirroring
until the local root, ACL, replication and byte budget are supplied; they are
local policy decisions rather than prerequisites for writing a manifest reader.
