# Architecture

How the experiment's code is arranged, what may depend on what, and which
bytes are frozen. Bazel package visibility enforces cross-concept imports, and
the evidence package records the source pins described below.

## Concept Packages

Each top-level directory under `autonomy/` is a concept package. Active imports
are package-qualified and declared in BUILD deps; packages are private by
default and grant visibility only to actual consumers.

| Concept | Owns |
| --- | --- |
| top-level entrypoints | Repository wrapper, tracer shell entrypoint and schema files |
| `training_execution/` | Balanced and sustained training execution, scoring, admission and controller workflows |
| `studies/` | Cross-concept study orchestration, study verifiers and closed procedure records |
| `association/` | Association runtime contracts and provenance |
| `evaluation/` | Metric/evaluator checks and perception gate audits |
| `inspection/` | Viewer/export tooling |
| `motion/` | Motion ingestion, causal projection and native metric tools |
| `range_view/` | Range frontend, range-pillar probes, sparse windows and fusion |
| `detection/` | Detector models, native box jobs, exports and diagnostics |
| `resources/` | Resource staging, archive, retention primitives and bounded worker admission |
| `retention/` | Sustained and native-cache publication and retention workflows |
| `segmentation/` | Semantic/SAM support, mask supervision and recovery checks |
| `camera/` | Camera data, sidecars, publication, replay and eviction |
| `geometry/` | Coordinate transforms, reconstruction, visibility and native range-grid shape math |
| `dataset/` | Scientific source admission, point/sidecar data, archives, tracer contracts and cloud setup |
| `insula/` | Launch-plan boundary, sandbox entry, rootfs recipes, Bazel launcher planning, M0 checks and staging leases |
| `evidence/` | Source snapshots, digests, regular-file checks, journal, tracker and publication |

Cross-concept workflows live at the concept level that owns the workflow. A
study that dispatches both `dataset` and `camera` commands belongs in
`studies/`; `dataset/` does not depend upward on `camera/` to run it. The
active range probes stay in `range_view/` and declare their downward
`geometry/` and `evidence/` dependencies. Producers that operate on oriented
boxes use the geometry box module; independent checkers keep their own second
implementations so producer errors can still be caught.

`research/` holds retained evidence, including frozen copies of sources, and is
outside the active import graph. `studies/*/procedure_records/` holds closed
procedure records: they remain byte-for-byte evidence, may contain historical
imports, and are not a reason to recreate old active package edges. The
retained architecture-adaptation composition still imports `range_view.RangePillar`;
that exception is modeled as an explicit BUILD dependency rather than a hidden
path rewrite.

## Active code and retained records

- **Active code** includes libraries, command entrypoints and controllers. Each
  belongs to the concept it implements. Its imports and subprocess inputs must
  be covered by the executable target's declared dependencies and data.
- **Closed procedure records** preserve historical study procedures, including
  unused contingency scripts. A retained file alone does not prove execution;
  the corresponding receipt supplies that evidence. These records remain in
  `procedure_records/` or `research/` and do not define active package edges.

Both kinds can be pinned by receipts. A source pin is the SHA-256 digest of a
source file recorded in a receipt; the file is *pinned* by that receipt. New
gate receipts bind a source snapshot, which is the frozen source/data closure of
the executable Bazel target. Historical schema 1 receipts use
component-relative paths; schema 2 source snapshot receipts use repository
paths rooted at `autonomy/`. The working tree is allowed to move forward even
when old receipts still pin earlier source bytes.

Production snapshot creation archives the executable target's transitive source
closure in content-addressed HDFS storage and verifies exact readback. Receipts
bind the archive digest, source pins and store descriptor. Offline tests inject
a local store explicitly; a failed HDFS operation does not become local-only
success.

Recovery verifies the admitted archive and materializes its original bytes.
An existing materialization must match the receipt; verification does not fill
in or overwrite a partial or altered tree. Historical receipts retain their
original schema, path interpretation and store contract. They are checked
against their admitted sources, not today's checkout or dependency inventory.

`evidence/source_snapshot.py` owns the shared file digest implementation, the
regular-file check, source snapshot creation and source pin verification.
Source closure tests assert behavior for executable targets; one-time migration
audits, not unit tests, check for old path hacks and duplicate helpers.

`autonomy/insula/launch_plan.py` is the only active code path that loads and
checks runtime locks, builds Insula launch plans, reads receipt mounts, renders
sandbox arguments, runs plans and records plan receipts. Callers pass structured
mounts, devices, environment and command data to that module; they do not splice
`bwrap` arguments or parse runtime locks themselves. Receipts with a
`launch_plan` record are checked by comparing that structured record with the
expected plan; the legacy command parser is used only for receipts that have no
plan record.

## Checks

Run source-pin commands from the `autonomy/` package root. Run Bazel component
checks from the repository root; the wrapper enters the recorded Insula rootfs.

```bash
cd autonomy
python3 -m evidence.pins status [PATH ...]  # which receipts pin a file
python3 -m evidence.pins check [--base REV] # source pins a change touches
cd ..
./bazelw --emit-plan test //autonomy/...          # inspect structured Insula launch-plan data
./bazelw test //autonomy/...                      # default perception tests
```

`./bazelw test //autonomy/...` is the default component entry point. Targets
that need Torch, CUDA or a live-gate mount are excluded from that default and
run only through their explicit GPU or live gates. Use
`./bazelw test --config=cuda //autonomy/...` for the GPU rootfs when the B200
runtime is available.
