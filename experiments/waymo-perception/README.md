# Waymo perception pipeline

Status: planning and source-contract research.

Storage: the complete selected dataset lives in HDFS; a small local slice
targets two complete scenes with every available modality. HDFS paths, local
cache policy, byte budget and materialization defer to `~/workspace/waystone`;
Sureal validates and consumes its slice/inventory handoff.

Runtime constraint: no TensorFlow. The proposed first reader uses PyArrow
directly; later tensor processing uses Torch and/or JAX, without SDK imports.

## Set up GCS access

Run from the repository root in your own interactive terminal:

```bash
experiments/waymo-perception/setup-gcs.sh
```

The wizard installs a SHA-256-pinned Google Cloud CLI with bundled Python,
guides you through Waymo access and Google authentication, then verifies bucket
access. It stores its private configuration outside git under
`${XDG_CACHE_HOME:-$HOME/.cache}/sureal/gcs/config`, without changing your shell
or Python environment. Set an absolute `GCS_TOOL_ROOT` to use another tool root.
Linux x86_64 and host Bash, curl, tar, sha256sum and flock are required.

Reuse the same isolated CLI after setup:

```bash
experiments/waymo-perception/gcs.sh -- storage ls gs://waymo_open_dataset_v_2_0_1/
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

## Active design artifacts

- [Design spec](../../docs/superpowers/specs/2026-09-29-waymo-perception-data-pipeline-design.md)
- [Roadmap](roadmap.md)
- [Upstream contract research](research/upstream-contract.md)
- [Source and design review](research/design-review.md)
- [Implementation plan](../../docs/superpowers/plans/2026-09-29-waymo-perception-data-pipeline.md)

## Planned layout

```text
experiments/waymo-perception/
  README.md
  roadmap.md
  research/
  recipe.json
  dataset.lock.json
  result.schema.json
  report.schema.json
  run.sh
  enter.sh
  verify_recipe.py
  pipeline/
```

The JSON schemas, runner, environment, and pipeline code are intentionally not
created yet. They should be added after the access policy, runtime isolation,
and first manifest schema decisions are resolved.

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

[`viewer/`](viewer/README.md) exports a Waystone slice into static scene
bundles (PyArrow + NumPy, no TensorFlow) and renders them in the browser with
Three.js: fused LiDAR points, 3D/2D labels, calibrated camera frusta with the
real images, panoptic and LiDAR segmentation, keypoints, ego trajectory and
temporal accumulation. Bundles stay outside git under the viewer cache.

```bash
experiments/waymo-perception/viewer/run.sh setup
experiments/waymo-perception/viewer/run.sh export SLICE_DIR CONTEXT
experiments/waymo-perception/viewer/run.sh dev
```

## Current status

- Waymo terms were accepted and the isolated gcloud CLI is authenticated for
  `gs://waymo_open_dataset_v_2_0_1`.
- Waystone delivered an all-modality two-scene validation slice
  (`validation-two-scenes-20260929`, 17 components, 1.2 GB, SHA-256 receipt)
  under its cache root; the viewer exporter consumes it directly.
- The manifest pipeline described in the plan below is still unimplemented on
  this branch; the viewer is a self-contained consumer of the raw slice.
- The first task consumer is undecided. The recommended first product is a
  scene manifest that can later support reconstruction, BEV, fusion, or
  TorchTitan training exports.

## Non-goals

- Download the full Waymo dataset in the first pass.
- Accept dataset terms or credentials from code.
- Add Waymo dependencies to Surflo's base import path.
- Train a perception model before one-segment manifest validation exists.
- Claim benchmark quality from reader or conversion smoke tests.
