# Waymo perception roadmap

This roadmap replaces the parked TorchTitan `.scratch/waymo-perception/`
tracker as the active owner for the Waymo perception line of work.

## Investigation checkpoint — 2026-09-29

The acquire-first two-scene tracer is complete; see
[coverage and evidence](research/tracer-bullet-e2e.md). It establishes authenticated
GCS acquisition, Waystone-resolved HDFS storage/readback and an offline
Parquet reader over all 17 component families. Production handoff automation,
point conversion, temporal geometry and reduced-pilot model metrics remain
open. The statuses below describe those broader gates.

## Research charter

The [research-program draft](../../docs/superpowers/specs/2026-09-29-waymo-research-program-design.md)
defines hypotheses and scientific acceptance gates. R0 closes the remaining
dedicated-Insula and geometric tracer prerequisites before model training.
The two current validation scenes remain development fixtures.

## 01. Upstream contract research

Type: research
Status: open
Blocked by:

Question: what does the Waymo Open Dataset repository and first-party
documentation require from a SUREAL-local perception experiment?

Acceptance:

- Close every operational claim in `research/upstream-contract.md` against
  first-party sources.
- Identify dataset versions, split/access paths, SDK/runtime constraints,
  stable identities, sensor and label schemas, and evaluation entrypoints.
- Separate Waymo-general facts from SUREAL-specific assumptions.
- List unknowns that require user access or a downloaded sample.

## 02. Access and storage policy

Type: design
Status: open
Blocked by: 01

Question: what inventory and local-slice handoff will Waystone supply for the
complete HDFS dataset and an all-modality two-scene local slice?

Confirmed topology: complete dataset under HDFS, bounded complete scenes
locally. HDFS paths, local root, byte budget and materialization policy defer
to `~/workspace/waystone`; Sureal owns offline slice/manifest validation.

Acceptance:

- Decide whether the user provides local Waymo files, cloud credentials, or a
  small sample fixture.
- Define where caches, raw sample links, converted shards, manifests, and
  reports live.
- Define commit-eligible files versus ignored/generated files.
- Set reduced-pilot size limits and cleanup rules.
- Identify any human-only access steps that require a wizard.

## 03. Runtime isolation

Type: design
Status: open
Blocked by: 01

Question: should the Waymo SDK run in a dedicated Insula, a Python 3.10/3.11
venv, or a v2 Parquet-only path?

Acceptance:

- Use v2 Parquet directly without TensorFlow or Waymo SDK imports. Any later
  tensor processing uses Torch and/or JAX.
- Keep PyArrow and any Torch/JAX runtime isolated from Surflo's baseline;
  verify TensorFlow is absent, including transitive dependencies.
- Define networked stages and offline stages.
- Define the smallest `verify-env` command.

## 04. Scene manifest schema

Type: design
Status: open
Blocked by: 01, 02, 03

Question: what is the stable scene/frame/sensor manifest interface?

Acceptance:

- Define required identity fields: dataset version, split, segment context
  name, frame timestamp, sensor name, and optional object IDs.
- Define calibration, pose, coordinate-frame, and label-provenance fields.
- Define missing, unknown, uncollected, malformed, and contradictory states.
- Define lineage fields for source, converter, run, and parent manifest.
- Define deterministic ordering and validation rules.

## 05. One-segment probe

Type: prototype
Status: open
Blocked by: 02, 03, 04

Question: can the selected runtime read one accessible Waymo segment or v2
component shard and emit a deterministic manifest?

Acceptance:

- Add only the minimum runner/environment files needed for the probe.
- The probe runs through the selected SUREAL isolation entrypoint.
- The probe emits a compact report with source identity, row/frame counts,
  modality counts, label counts, runtime, and failure mode.
- The report is explicit when missing data or credentials block execution.

## 06. Reduced pilot

Type: task
Status: open
Blocked by: 05

Question: can a small fixed data budget be processed repeatably?

Acceptance:

- Define segment/frame/sensor budget and output-size ceiling before launch.
- Process the budget with staging, validation, and atomic promotion.
- Report completeness, malformed inputs, runtime, peak memory, artifact bytes,
  and schema validity separately.
- Do not claim training or perception quality.

## 07. Training bridge decision

Type: decision
Status: open
Blocked by: 06

Question: what should consume the stable Waymo output first?

Options:

- SUREAL reconstruction or scene-hypothesis experiment.
- Maintained reference adapter.
- TorchTitan export for distributed model training.

Acceptance:

- Select one first consumer and explain why.
- Define the minimal interface from manifest/output to that consumer.
- If TorchTitan is selected, create a new TorchTitan bridge ticket that depends
  on the SUREAL output contract instead of duplicating Waymo parsing there.
