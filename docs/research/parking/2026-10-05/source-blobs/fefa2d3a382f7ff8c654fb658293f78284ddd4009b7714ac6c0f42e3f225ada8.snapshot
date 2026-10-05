# Waymo Perception Data Pipeline Design

**Date:** 2026-09-29

**Status:** Draft route after repo-fit check; awaiting design review
**Owner repo:** Sureal
**Supersedes:** parked TorchTitan `.scratch/waymo-perception/` scaffold
**Experiment entry:** `experiments/waymo-perception/README.md`

## Purpose

Build a Waymo Open Dataset perception line of work as a Sureal experiment before
adding any TorchTitan training bridge.

Waymo is primarily a calibrated, multi-sensor, metric scene dataset. Sureal
already owns the relevant seams: camera geometry, metric depth/range, LiDAR
summaries, object IDs, artifact locks, Insula execution, immutable run outputs,
and evidence-bounded 3D pathway reporting. TorchTitan should consume a later
stable output only if the selected task becomes a distributed training problem.

## Repository Ownership Decision

The first module should live in Sureal, not TorchTitan.

Reasons:

- Sureal's mission is geometric reconstruction to persistent generative scene
  representations from incomplete visual evidence.
- The 3D pathway already defines the questions every scene module answers:
  evidence, observability, representation, inference mode, objectives, out of
  support behavior, and controlled failure.
- Existing experiments already handle cameras, metric depth/ray distance,
  normals, stable object IDs, surface samples, visibility, immutable artifacts,
  hash-verified inputs, and Insula execution.
- Waymo's Perception dataset exposes calibrated cameras, LiDAR, poses, object
  labels, segmentation, and task metrics. Those are closer to Sureal's scene
  and representation contracts than to TorchTitan's core trainer loop.
- TorchTitan's useful role is downstream: train a model on a stable exported
  data contract, or compare distributed training behavior once Sureal has
  proven the scene/data semantics.

## User-confirmed runtime and storage requirements

These requirements supersede the draft alternatives below:

- No TensorFlow in runtime, transitive dependencies, fallbacks or verification.
  Use PyArrow directly for Parquet I/O; tensor processing uses Torch and/or JAX.
- Store the complete selected dataset under HDFS and retain a small local slice,
  initially targeting two complete scenes with every available modality, sensor
  and native frame. A smoke-reader frame limit does not reduce stored scene data.
- Defer HDFS namespace, local slice path, byte budget and materialization policy
  to `~/workspace/waystone`. Sureal consumes and validates its local slice and
  inventory/lineage handoff; it does not duplicate HDFS transfer/authentication.
- Measure component coverage before choosing the scenes. Report modalities not
  collected for a scene or not included in the selected release explicitly;
  never equate two scenes with universal per-frame modality coverage.

See the [implementation plan](../plans/2026-09-29-waymo-perception-data-pipeline.md)
for the proposed handoff and separate storage/reader completeness gates.

## Current Source Facts

These are preliminary source checks and must be closed by a dedicated research
ticket before implementation. The active preliminary note is
`experiments/waymo-perception/research/upstream-contract.md`.

- Upstream repository:
  `https://github.com/waymo-research/waymo-open-dataset`, `master` observed at
  commit `99a4cb3ff07e2fe06c2ce73da001f850f628e45a`.
- The upstream README describes three datasets: Perception, Motion, and
  End-To-End Driving. The Perception dataset is the relevant first target.
- The upstream README says the repository contains dataset format definitions,
  evaluation metrics, and TensorFlow helpers.
- Code license is Apache 2.0 except `src/waymo_open_dataset/wdl_limited`; the
  dataset itself is governed by separate Waymo Open Dataset terms.
- Current Waymo access/download pages redirected to login in this unauthenticated
  session, so data access remains a human-owned setup blocker.
- Upstream SDK evidence points at Python 3.10/3.11-era dependency constraints.
  `src/waymo_open_dataset/requirements.txt` is generated with Python 3.10 and
  includes TensorFlow 2.13.0, protobuf 3.20.3, numpy 1.23.5, and pyarrow 16.0.0.
- The Python package family observed on the package index is
  `waymo-open-dataset-tf-2-12-0` / `waymo-open-dataset-tf-2-11-0`, not a plain
  `waymo-open-dataset` package.
- The TorchTitan rootfs uses Python 3.12 and did not already have TensorFlow or
  `waymo_open_dataset`; that specific rootfs is not a good default SDK runtime.

## First Seam

Create a Sureal experiment directory:

```text
experiments/waymo-perception/
  README.md
  recipe.json
  dataset.lock.json
  result.schema.json
  report.schema.json
  run.sh
  enter.sh
  verify_recipe.py
  pipeline/
  research/
```

The first deep module should be a dataset-introspection and manifest module:

```text
Waymo source segment(s) -> stable scene/frame manifest -> validation report
```

Its interface should stay small:

- input: dataset version, split, source root or sample file, selected modalities;
- output: deterministic manifest rows and a validation result;
- invariants: stable scene/frame/sensor identities, calibrated metric frames,
  explicit missing/unknown/uncollected states, and no payload redistribution.

Do not start with a training dataloader. The first useful product is a verified
scene/data contract that every later model adapter can consume.

## V1 Task Recommendation

Use Waymo Perception v2 if access permits, because the preliminary source pass
found that v2 uses modular Apache Parquet components and may allow selective
component reads without parsing every v1 TFRecord payload. Any later v1 TFRecord fallback must be designed without TensorFlow or SDK
execution; the first slice uses v2 Parquet directly.

The first perception task should be selected after the research closeout, but
the default recommendation is a geometry-first slice:

- read calibrated frame identity;
- read camera metadata and one or more camera images;
- read LiDAR range or point summary;
- read 3D object labels;
- emit a manifest that can drive scene reconstruction, BEV, or fusion
  experiments without committing to a training model.

Camera-only 2D detection is simpler, but it throws away the 3D structure that
makes Waymo a good Sureal fit.

## Human-Owned Inputs

The design cannot proceed to runnable conversion until these are resolved:

- dataset terms acceptance and access path;
- local sample segment or v2 component shard;
- allowed cache root and size budget;
- whether outputs may contain derived thumbnails, label summaries, or only
  metadata/manifests;
- Waystone-provided HDFS inventory, local slice receipt and measured byte budget.

If access requires dashboard steps, generate a wizard rather than embedding
credentials or manual instructions in the code.

## Execution Contract

Follow SUREAL's existing experiment style:

- host scripts build environments, establish mounts, and dispatch commands;
- network is allowed only in explicit build/fetch stages;
- validation and conversion run offline once data is staged;
- outputs write to staging, validate schema and hashes, then promote atomically;
- large datasets and converted payloads live under cache roots, not git;
- compact machine-readable results and source/asset locks are tracked.

Use a dedicated Parquet-reader environment without TensorFlow or Waymo SDK
imports, isolated from the Surflo baseline. The implementation plan recommends
a CPU Insula entered by `experiments/waymo-perception/enter.sh`. Waystone owns
networked HDFS acquisition/materialization; Sureal processing stays offline.

## First Decision Tickets

The active roadmap lives at `experiments/waymo-perception/roadmap.md`.

1. **Upstream contract research.** Close the preliminary source facts against
   first-party repository files, tutorials, release notes, protos, and terms.
2. **Access and storage policy.** Decide sample/data source, cache root,
   output-retention limits, and redistribution rules.
3. **Runtime isolation.** Decide whether the Waymo SDK gets a dedicated Insula,
   a Python 3.10/3.11 venv, or a Parquet-only path.
4. **Scene manifest schema.** Define stable IDs, modality fields, calibration,
   pose, coordinate frame, labels, missing-data semantics, and lineage.
5. **One-segment probe.** Read one accessible segment/shard and emit a
   deterministic manifest plus validation report.
6. **Reduced pilot.** Process a small, fixed segment budget and report
   completeness, runtime, artifact size, and schema validity.
7. **Training bridge decision.** Only after the manifest exists, decide whether
   the first consumer is Surflo/Sureal, a maintained reference adapter, or a
   TorchTitan export.

## Non-Goals

- Full Waymo conversion in the first pass.
- Accepting Waymo terms or credentials on behalf of the user.
- Training a perception model before the manifest and runtime are proven.
- Adding Waymo dependencies to Surflo's base import path.
- Moving Waymo-specific parsing into TorchTitan core.
- Claiming Waymo perception quality from a smoke reader.

## Verification Plan

Before implementation:

```bash
git diff --check
```

First runnable gate after the design is approved:

```bash
experiments/waymo-perception/run.sh emit-plan
experiments/waymo-perception/run.sh verify-env
experiments/waymo-perception/run.sh inspect-one --sample /path/to/sample
experiments/waymo-perception/run.sh validate --run-id waymo-one-segment
```

The exact commands should be updated once the runtime isolation decision is
made. A passing `inspect-one` proves only SDK/runtime/data plumbing and manifest
validity. It is not a model-training or benchmark-quality claim.
