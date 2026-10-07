# Waymo perception pipeline

Status: two-scene acquisition and offline processing tracer completed; production pipeline remains planned.

Storage target: the complete dataset lives in HDFS. The acquired slice contains
two complete scenes with all 17 available component families, mirrored to HDFS. HDFS paths, local
cache policy, byte budget and materialization defer to `~/workspace/waystone`;
Sureal validates and consumes its slice/inventory handoff.

Runtime constraint: no TensorFlow. The proposed first reader uses PyArrow
directly; later tensor processing uses Torch and/or JAX, without SDK imports.

See [real-data investigation evidence](research/tracer-bullet-e2e.md) for the
local slice, commands, coverage, unresolved associations and repeatability checks.

## Set up GCS access

Run from the repository root in your own interactive terminal:

```bash
autonomy/dataset/setup-gcs.sh
```

The wizard installs a SHA-256-pinned Google Cloud CLI with bundled Python,
guides you through Waymo access and Google authentication, then verifies bucket
access. It stores its private configuration outside git under
`${XDG_CACHE_HOME:-$HOME/.cache}/sureal/gcs/config`, without changing your shell
or Python environment. Set an absolute `GCS_TOOL_ROOT` to use another tool root.
Linux x86_64 and host Bash, curl, tar, sha256sum and flock are required.

Reuse the same isolated CLI after setup:

```bash
autonomy/dataset/gcs.sh -- storage ls gs://waymo_open_dataset_v_2_0_1/
```

No dataset payloads are downloaded during setup. See the
[bootstrap verification note](research/gcs-bootstrap.md) for artifact pins and
the precise runtime isolation boundary.

This experiment is the SUREAL home for processing Waymo Open Dataset
Perception data into scene-centric artifacts. It is not a TorchTitan training
entrypoint yet. TorchTitan should consume a later stable export only after this
experiment proves the dataset, scene, and lineage contracts.

## Why this lives here

Waymo Perception is a calibrated multi-sensor scene dataset. The useful first
seam is therefore a scene/frame manifest, not a distributed training dataloader.
SUREAL already owns the relevant machinery for metric cameras, range evidence,
object identities, immutable experiment outputs, Insula execution, and
evidence-bounded 3D reports.

## Research program

The [Perception-first research program](../docs/superpowers/specs/2026-09-29-waymo-research-program-design.md)
turns the acquired slice into gated geometry, semantic/detection, fusion, memory
and separate downstream-task experiments. Concrete model bases are
[PointPillars → CenterPoint head → SWFormer](research/lidar-encoder-bases.md)
[RSN and range-view features](research/range-view-bases.md),
and [FCOS3D / BEVDepth / BEVFormer with LET evaluation](research/camera-encoder-bases.md).
The dedicated Insula sensor-to-scene tracer and subsequent scoped milestones
have retained live evidence. The [task index](research-task-index.md) records
current acceptance and remaining research gates.

## Active design artifacts

- [Design spec](../docs/superpowers/specs/2026-09-29-waymo-perception-data-pipeline-design.md)
- [Roadmap](roadmap.md)
- [Upstream contract research](research/upstream-contract.md)
- [Source and design review](research/design-review.md)
- [Implementation plan](../docs/superpowers/plans/2026-09-29-waymo-perception-data-pipeline.md)

## Current layout

The [Architecture note](ARCHITECTURE.md) records the current code areas,
layering, source-pin impact, and repository-root check commands. Retained
receipts keep their historical paths; current commands use `autonomy/`.

## Intended first module

```text
Waymo source segment or v2 component shard
  -> stable scene/frame/sensor manifest
  -> validation report
```

The manifest should preserve:

- dataset version and split;
- segment context name and frame timestamp;
- camera and LiDAR sensor identity;
- calibration and pose provenance;
- label family and object identity where available;
- source path, size, checksum or upstream revision;
- converter version and run identity;
- explicit missing, unknown, uncollected, and malformed states.

## Web 3D viewer

[`inspection/viewer/`](inspection/viewer/README.md) exports a Waystone slice into static scene
bundles (PyArrow + NumPy, no TensorFlow) and renders them in the browser with
Three.js: fused LiDAR points, 3D/2D labels, calibrated camera frusta with the
real images, panoptic and LiDAR segmentation, keypoints, ego trajectory and
temporal accumulation. Bundles stay outside git under the viewer cache.

```bash
autonomy/inspection/viewer/run.sh setup
autonomy/inspection/viewer/run.sh export SLICE_DIR CONTEXT
autonomy/inspection/viewer/run.sh dev
```

## Current gates

- Waystone delivered and HDFS-mirrored the all-modality two-scene development
  slice; the source inventory and offline tracer evidence are retained.
- The locked, TensorFlow-free Insula reader and scoped processing checks have
  live receipts. These establish engineering correctness within their declared
  scope, not full-dataset quality or a production pipeline.
- Complete resource/backend/retention/runner admission remains required before
  resuming the frozen four-recipe balanced16 sweep. Detection, segmentation,
  SAM and downstream forecasting retain separate scientific acceptance gates.

## Non-goals

- Download the full Waymo dataset in the first pass.
- Accept dataset terms or credentials from code.
- Add Waymo dependencies to Surflo's base import path.
- Train a perception model before one-segment manifest validation exists.
- Claim benchmark quality from reader or conversion smoke tests.

## Run architecture experiments

Each tested direction and planned follow-up has its own [experiment document](architecture/README.md).
The dispatcher has a source-bound live CPU admission for `list` and
`show residual_bev`. The underlying historical seven-stage experiment runners
retain their separate live receipts; catalog checks do not repeat or extend
those scientific measurements. The complete balanced16 resource/continuation
gate remains open. See the closeout inventory for scoped evidence and blockers.

```bash
python autonomy/architecture.py list
python autonomy/architecture.py run residual_bev --run-id residual-trial01
python autonomy/architecture.py verify residual_bev --run-id residual-trial01
```

Training, checkpoint replay and native scoring/audits run live Insula. Historical results remain unchanged; planned ideas are refused until implemented. See the guide for prerequisites, budgets, logs and acceptance gates.
