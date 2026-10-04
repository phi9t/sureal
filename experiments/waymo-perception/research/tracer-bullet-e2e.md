# Two-scene Waymo processing investigation

Date: 2026-09-29. Worktree: `.worktrees/waymo-tracer`, branch `work/waymo-tracer`.

The real-data tracer acquires two complete validation scene bundles, mirrors
and reads them back through Waystone/HDFS, then processes every native row
in an offline namespace. Production ingestion, point reconstruction, motion
compensation, model execution and training are later implementation-plan work.
This investigation uses PyArrow/NumPy/Pillow; TensorFlow and the Waymo SDK are
absent. Future tensor processing remains Torch and/or JAX.

## Acquisition and storage

The validation inventory contains 202 scenes, 3,434 objects and 17 families,
totaling 128,583,245,118 bytes. The selected contexts are
`5847910688643719375_180_000_200_000` (198 frames) and
`8137195482049459160_3100_000_3120_000` (199 frames). Smaller bundles had empty
sparse annotation files; these scenes have nonempty keypoint and segmentation
families. All modalities being represented does not mean every annotation
exists on every frame or sensor.

The local slice is
`~/.cache/waystone/waymo-perception/slices/validation-two-scenes-20260929`:
34 Parquet objects, 1,200,154,353 bytes, under a 2 GiB acquisition budget.
Each download is GCS-generation-pinned and checked against provider MD5,
size and a recorded SHA-256. `dataset.lock.json` stores the selected object
provenance; the slice's `slice.json` is its authoritative acquisition receipt.

Waystone resolved the namespace
`hdfs://harunava/user/tiger/waystone/sureal/waymo/perception/v2.0.1`.
Objects are at `raw/validation/{component}/{context}.parquet` beneath it.
All 34 were uploaded with Waystone MD5 verification, downloaded again and
compared byte-for-byte through SHA-256 and size. The receipt was uploaded to
`manifests/validation-two-scenes-20260929.json`. Only this cohort was mirrored;
the remaining validation inventory and complete dataset were not ingested.
The local path follows Waystone's cache convention; Waystone does not yet
publish a Waymo-specific materialization contract.

## Processing and validation

The tracer preserves each component's native keys rather than multiplying
sensor and object rows. It decodes every JPEG/PNG payload, summarizes every
range-image payload, records metadata and missing-payload states, checks rigid
transforms, camera dimensions, auxiliary range-image dimensions and references.
Source content hashes and the receipt are revalidated. Independent validation
rejects duplicate IDs/native keys, incorrect source lineage and omissions or
substitutions by reconciling manifest keys with the source Parquet keys.

Outputs are staged, validated, then atomically promoted into a new run directory.
Each directory contains `manifest.jsonl`, `sources.json`, `report.json` and
`result.json`, with JSON schemas, artifact digests, environment versions and
implementation hashes. The manifest contains summaries and metadata rather
than exported raw images or reconstructed points.

The runtime is a bubblewrap `--unshare-all` namespace with a private HOME,
read-only sources, a writable output parent and no GCS credential mount.
`verify-env` checks its distinct network namespace and real Parquet/image
round trips. Its interpreter and hash-pinned dependencies are isolated;
host `/usr`, dynamic libraries and bubblewrap remain runtime prerequisites.
Python 3.12.13 matches Waystone's observed runtime; dependencies are PyArrow
25.0.1, NumPy 2.5.3, Pillow 12.3.0 and jsonschema 4.26.0.

## Findings and limits

There are 397 frames, five cameras and five LiDAR sensors per frame. Camera
segmentation covers 99 frames per scene (495 camera rows each); LiDAR
segmentation has 30 TOP sensor rows per scene. Keypoint labels are sparse.
No missing pose-frame or sensor-calibration references were found.

Of 7,074 camera-to-LiDAR associations, all camera targets exist, but 337
same-frame LiDAR box targets are absent (210 and 127 by scene). Of these,
305 reference LiDAR object IDs seen in other frames in their scene; 32 do not.
The first strict exploratory pass stopped on this upstream condition and
promoted no output. The completed tracer preserves those associations as
unknown, records the warning and never substitutes another frame's box.
`passed=true` means structural/payload plumbing validation;
`association_resolution=incomplete` explicitly records this limitation.
The cause of missing LiDAR targets is unresolved.

Rigid transform orthogonality errors are at floating-point scale (maximum
4.44e-16). This does not establish motion-compensated geometry correctness.
There are no point-cloud, model-quality or task-metric claims.

## Reproduce locally

From this worktree, after installing uv and bubblewrap:

```bash
uv venv --python 3.12.13 "$HOME/.cache/waystone/waymo-perception/probe-venv"
uv pip sync --python "$HOME/.cache/waystone/waymo-perception/probe-venv/bin/python" experiments/waymo-perception/requirements-tracer.lock
experiments/waymo-perception/tracer.sh verify-env
slice="$HOME/.cache/waystone/waymo-perception/slices/validation-two-scenes-20260929"
run="$HOME/.cache/waystone/waymo-perception/runs/my-new-run"
experiments/waymo-perception/tracer.sh inspect "$slice" "$run"
experiments/waymo-perception/tracer.sh validate "$slice" "$run"
```

Inspection requires a fresh run name. Acquisition is a separate networked
operation using `gcs.sh` and Waystone; processing never authenticates.

## Native-row coverage

| Component | Rows |
|---|---:|
| camera_box | 36,700 |
| camera_calibration | 10 |
| camera_hkp | 286 |
| camera_image | 1,985 |
| camera_segmentation | 990 |
| camera_to_lidar_box_association | 7,074 |
| lidar | 1,985 |
| lidar_box | 38,363 |
| lidar_calibration | 10 |
| lidar_camera_projection | 1,985 |
| lidar_camera_synced_box | 24,356 |
| lidar_hkp | 36 |
| lidar_pose | 397 |
| lidar_segmentation | 60 |
| projected_lidar_box | 28,594 |
| stats | 397 |
| vehicle_pose | 397 |
| **Total** | **143,625** |

## Final verification

All 16 behavioral/runtime/bootstrap tests pass, including three reproduced
independent-validator defects (duplicate keys, fabricated lineage and substituted
frame keys). Shell syntax, ShellCheck and whitespace checks pass.

Two final real-data runs, `tracer-final-a` and `tracer-final-b`, each passed with
143,625 records. Their 142,876,483-byte manifests are byte-identical:
`70190074c7d443632523a5c3273d5ead74f4fcddea653addee3a2fa2efa01bcf`. Source receipts and implementation
hashes also match. Reports/results contain varying resource measurements and
are intentionally not byte-identical. See [machine-readable evidence](tracer-reproducibility.json).

Reported inspection times were 104.66 and 106.65 seconds; process peak RSS was
1,064,357,888 and 1,071,968,256 bytes. Timing excludes the subsequent independent
validation pass. These are observations, not enforced memory guarantees.
Outputs live under `~/.cache/waystone/waymo-perception/runs/`.
