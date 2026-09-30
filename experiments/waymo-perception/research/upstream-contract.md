# Waymo upstream contract notes

Status: source-backed orientation for the first `autonomy-pathway` milestone.
Upstream code was inspected at commit
`99a4cb3ff07e2fe06c2ce73da001f850f628e45a` (the `master` HEAD observed on
2026-09-29). Statements under **Upstream facts** describe contracts owned by
Waymo or Google; statements under **Proposed SUREAL policy** are local design
choices and must not be mistaken for upstream guarantees.

## Primary sources

- [Waymo Open Dataset repository README](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/README.md)
- [Perception v1 `Frame` schema (`dataset.proto`)](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/dataset.proto)
- [Perception v1 tutorial](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/tutorial/tutorial.ipynb)
- [Perception v2 tutorial](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/tutorial/tutorial_v2.ipynb)
- [v2 component tags](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/v2/__init__.py)
- [v2 key hierarchy](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/v2/perception/base.py)
- [v2 merge implementation](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/v2/dataframe_utils.py)
- [Waymo download page](https://waymo.com/open/download/), [dataset overview](https://waymo.com/open/about/), [terms](https://waymo.com/open/terms/), and [FAQ](https://waymo.com/open/faq/)
- Google Cloud documentation for [authentication](https://cloud.google.com/storage/docs/authentication) and [downloading objects](https://cloud.google.com/storage/docs/downloading-objects)

## Upstream facts

### GitHub is the SDK, not the dataset

The GitHub repository supplies format definitions, evaluation code, and
TensorFlow helpers. It does not contain the Perception dataset bytes. Its code
is Apache 2.0 except for `src/waymo_open_dataset/wdl_limited`; the dataset is
subject to separate Waymo terms. Therefore GitHub authentication, if used,
only retrieves the source repository. The repository is currently public, so a
normal HTTPS `git clone` succeeds without GitHub credentials; authenticated
GitHub access does not grant dataset access.

Waymo's download page says the dataset files live in Google Cloud Storage. The
current Perception links resolve to these authenticated bucket views:

- v1.4.3, with maps: `gs://waymo_open_dataset_v_1_4_3`
- v2.0.1, modular without maps: `gs://waymo_open_dataset_v_2_0_1`

The download UI redirects an unauthenticated user to Google login, and an
anonymous JSON API listing of the v2 bucket returns `401`. Waymo's terms page
requires a Google account, sign-in at the Waymo Open Dataset site, and
acceptance of the dataset license. Google Cloud documents `gcloud auth login`
for CLI user credentials and `gcloud storage cp` for authenticated object
downloads. These Google/Waymo credentials are independent of GitHub auth.

The FAQ explicitly says the dataset license has distribution limitations and
is not an open-source license. Copying authorized data into HDFS does not alter
those terms or make the HDFS tree redistributable.

### Published scope and size information

Waymo documents 2,030 Perception segments of 20 seconds each, collected at
10 Hz, totaling about 390,000 frames. As of the source check, the official
download page names v1.4.3 and v2.0.1 as the current Perception releases and
describes v2 as modular and without maps.

No official byte total or per-component byte breakdown was found in the
official pages or pinned repository. Storage planning must therefore begin
with an authenticated object inventory (object name, size, generation/checksum)
for the selected release, split, and components rather than relying on an
unsourced whole-dataset size estimate.

### v1 representation: TFRecord of serialized `Frame` protos

The v1 tutorial reads an uncompressed `tf.data.TFRecordDataset`; every record
is parsed as `waymo_open_dataset.dataset_pb2.Frame`. A `Frame` contains:

- `context`, shared by frames from one driving segment;
- `timestamp_micros`, the start time of the first top-LiDAR scan;
- the frame vehicle pose;
- camera images and LiDAR range-image data;
- camera and LiDAR calibrations in the context;
- native 3D LiDAR labels, projected LiDAR labels, camera labels,
  segmentation labels, no-label zones, and related metadata.

The proto warns that `timestamp_micros` does not exactly correspond to the
provided frame pose. The frame pose defines the coordinate system in which 3D
laser labels are expressed. A processor must retain this temporal and
coordinate-frame provenance rather than treating all fields as if they were
sampled at one timestamp.

The stable v1 frame identity is `(release, split, context.name,
timestamp_micros)`. Sensor-specific records add the camera or LiDAR enum; label
records add their upstream object ID. A TFRecord file is a container of many
frame records, not itself the semantic identity of a frame.

### v2 representation: component Parquet tables

The v2 tutorial defines v1 as the earlier `Frame` protobufs serialized in
TFRecord and v2 as a column-oriented Parquet representation split into
components. It says v2-supported values correspond to fields in v1.4.2 through
the compatibility layer. Raw tables can be read without protobufs by any
Parquet reader; Waymo demonstrates Dask for larger-than-memory work and Pandas
for a segment that fits in memory.

The physical convention is one Parquet file per component and context:

```text
{dataset_root}/{component_tag}/{segment_context_name}.parquet
```

For example, the same context may have sibling files under `camera_image/`,
`lidar/`, and `lidar_box/`. The pinned API publishes these component tags:

```text
camera_box                         camera_calibration
camera_hkp                         camera_image
camera_segmentation                camera_to_lidar_box_association
lidar_box                          lidar_calibration
lidar_camera_projection            lidar_camera_synced_box
lidar                              lidar_hkp
lidar_pose                         lidar_segmentation
projected_lidar_box                stats
vehicle_pose                       object_asset_auto_label
object_asset_camera_sensor         object_asset_lidar_sensor
object_asset_refined_pose          object_asset_ray
object_asset_ray_compressed
```

Not every research task needs every component. In particular, the download
page's “without maps” qualification means v2 must not be assumed to replace
v1.4.3 for map-dependent work.

### v2 identity, granularity, and joins

All v2 key columns use the `key.` prefix. The key hierarchy defines the row
grain:

| Grain | Key columns |
| --- | --- |
| segment | `segment_context_name` |
| frame | segment key + `frame_timestamp_micros` |
| segment/LiDAR calibration | segment key + `laser_name` |
| frame/LiDAR | frame key + `laser_name` |
| segment/camera calibration | segment key + `camera_name` |
| frame/camera | frame key + `camera_name` |
| 3D scene object | frame key + `laser_object_id` |
| camera object | frame/camera key + `camera_object_id` |

LiDAR labels intentionally do **not** carry `laser_name`: they describe the
whole 3D scene rather than one LiDAR. Camera-to-LiDAR associations bridge the
distinct camera and laser object IDs.

Waymo's `v2.merge` joins on the intersection of `key.*` columns. Its default is
an inner join. When two inputs have different key sets, callers can request
grouping on the shared keys so unmatched dimensions become lists; nullable
flags select left, right, or outer behavior. This is important: a naive merge
at frame grain can create a camera-by-LiDAR or sensor-by-object cross product.
Processors should declare the expected input and output grain for every join
and validate uniqueness/cardinality before materializing it.

## Proposed SUREAL/HDFS policy

The following is a proposed local policy, not a Waymo requirement.

### Acquisition boundary

1. Pin the SDK clone by commit SHA in experiment metadata. GitHub auth may be
   used by local infrastructure, but must not be described as dataset auth.
2. Have a human accept the Waymo dataset terms with the Google account that
   will authorize the transfer. Do not automate acceptance or store browser
   cookies, OAuth refresh tokens, or service-account keys in the repository or
   HDFS.
3. Use authenticated Google Cloud tooling to inventory the v2.0.1 bucket
   before downloading. Record object path, byte size, object generation, and
   provider checksum where available.
4. Download only an allowlisted split, component set, and context set to a
   bounded local staging directory, verify it, then copy it to HDFS. A direct
   GCS-to-HDFS transfer can be evaluated later, but the first probe should keep
   the trust boundary and failure recovery observable.

### HDFS layout

Preserve upstream Parquet files byte-for-byte in an immutable raw zone:

```text
{hdfs_root}/waymo/perception/v2.0.1/raw/{split}/{component}/{context}.parquet
{hdfs_root}/waymo/perception/v2.0.1/manifests/{acquisition_id}.jsonl
```

Keep release and split explicit even if the GCS object path already implies
them. The manifest should include the upstream GCS URI and generation,
component, context, byte size, provider checksum, local/HDFS checksum, ingest
time, SDK commit, and license/access provenance without credentials. Never
rewrite raw files in place. Put normalized or compacted derivatives under a
separate `derived/{pipeline_version}/...` prefix and retain the source object
identities used to build them.

HDFS replication and ACLs must be chosen deliberately because they multiply
storage use and control whether copying remains internal to authorized users.
Do not make the raw prefix world-readable. Treat removal, sharing, and
retention as dataset-license decisions, not ordinary public artifact handling.

### Selective working-set ladder

Start small and expand only from measured inventories:

1. **Schema probe:** one context, metadata/calibration/pose plus one sensor and
   its labels.
2. **Join probe:** a few contexts containing the components required to prove
   camera, LiDAR, label, and association cardinalities.
3. **Pilot:** a fixed, manifested context cohort across train/validation with
   exact byte and row counts.
4. **Research working set:** only the components required by a named
   `autonomy-pathway` hypothesis.

For a first multimodal orientation probe, a reasonable allowlist is
`camera_calibration`, `lidar_calibration`, `vehicle_pose`, `stats`,
`camera_image`, `lidar`, `camera_box`, `lidar_box`, and
`camera_to_lidar_box_association`. Segmentation, flow, keypoints, projections,
and object assets should be added only when a research question needs them.

### Validation gates

An acquisition is usable only when:

- every copied object matches its recorded byte count and checksum;
- Parquet footers and Arrow schemas are readable;
- the path context matches `key.segment_context_name` in every row;
- required key columns are non-null and unique at the component's declared
  grain;
- cross-component joins have measured cardinalities and no unexplained row
  multiplication;
- calibrations, poses, timestamps, sensor enums, and object IDs remain present
  in derived records; and
- rerunning the acquisition against the same manifest is idempotent.

## Implications for the first `autonomy-pathway` milestone

The first milestone should map both representations but implement the probe on
v2.0.1 Parquet. It should produce an authenticated inventory, an immutable HDFS
working set, a machine-readable schema/key report, and one executable join
probe over a fixed context cohort. v1.4.3 remains the compatibility and map
reference; it does not need to be mirrored in full before the initial v2 probe.

Open decisions that require local evidence are the HDFS root/ACL/replication
settings, available Google Cloud credential path on the transfer host, exact
GCS split prefixes, and byte budget after authenticated inventory. Dataset byte
size and component coverage must not be guessed before that inventory exists.
