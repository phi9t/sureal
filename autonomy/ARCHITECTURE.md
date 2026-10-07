# Architecture

How the experiment's code is arranged, what may depend on what, and which
bytes are frozen. The three rules below are checked by `autonomy/tools/`, so
this file describes them; it does not enforce them.

## Layers

Each top-level directory under `autonomy/` is an *area*. An area may import its
own modules and any area on a lower row. Areas on the same row are peers and do
not import each other. The order is declared in
[`tools/layers.py`](tools/layers.py).

| Layer | Areas | Role |
| --- | --- | --- |
| 15 | top-level scripts, `scripts/`, `analysis/`, `tests/`, `tools/` | Gate runners, operations, diagnostics, development checks |
| 14 | `cohort/` | 16-scene cohort studies: balanced and sustained training, scoring, audits |
| 13 | `advanced/` | Expanded fixed-batch architecture suite |
| 12 | `tier1/` | Fixed-batch architecture overfit suite |
| 11 | `architecture/` | Experiment catalog and runner |
| 10 | `gpu/`, `evaluation/`, `tracking/`, `association/`, `inspection/` | Model workers, metric contracts, inspection and standalone tools |
| 9 | `motion/` | Motion ingestion, causal projection and native metric tools |
| 8 | `pipeline/` | Remaining readers, encoders and archives |
| 7 | `detection/` | Pillar detection and native training-box tools |
| 6 | `resources/` | Measured bounded execution, retention, replay continuation and native-receipt binding |
| 5 | `segmentation/` | Semantic and instance segmentation, masks and recovery |
| 4 | `camera/` | Camera data, sidecars and projection tools |
| 3 | `geometry/` | Coordinate transforms, visibility and native range-grid shape math |
| 2 | `dataset/` | Scientific dataset components, archives, eviction and cloud setup |
| 1 | `insula/` | Sandbox entry, rootfs identity, M0 checks and staging leases |
| 0 | `evidence/` | Snapshots, digests, regular-file checks, journal, tracker and publication |

`research/` holds retained evidence, including frozen copies of sources, and is
outside the layering.

One upward import exists: `tier1/prepare_v3.py` imports `cohort/balanced.py`.
It is listed as the only entry of `KNOWN_UPWARD`.

Cross-area imports are qualified (`from geometry.geometry import ...`). A bare
import (`import models`) resolves through whichever directories a script put on
`sys.path`, and 14 module names (`models`, `catalog`, `train`, `prepare`, ...)
exist in more than one area. The check refuses a bare import whose name is
defined by more than one other area.

## Two kinds of source

- **Library code** is imported by other modules: most of `pipeline/`, the model
  and variant modules in `gpu/`, `tier1/` and `advanced/`, the stage backend in
  `resources/`, the Insula sandbox helpers in `insula/`, and the journal and
  snapshot tools in `evidence/`.
- **Procedure records** are scripts that ran one gate or one study stage and
  wrote a receipt containing their own digest: the top-level `verify-*.py` and
  `publish-*.py`, the hyphenated workers in `gpu/` and `cohort/`, and the
  `_v2`/`_v3` successors beside them.

Both kinds are pinned by receipts. Almost every tracked file outside
`research/` has the SHA-256 of its current bytes recorded in at least one
retained receipt (`autonomy/evidence/pins.py status` prints the count per area). Two
validators also require an exact file inventory, so adding a file there changes
what they admit:

- `cohort/sustained_sources.py`: every `*.py` under `dataset/`, `geometry/`,
  `segmentation/`, `resources/`, `pipeline/`, `insula/`, `gpu/`, `tier1/`
  and `cohort/`, plus the source snapshot helper, which
  `cohort/sustained_controller_backend.py` freezes for each sustained run;
- `resources/sources.py`: every `*.py` under `resources/`.

This is why a changed procedure appears as a new `_v2` file instead of an edit:
editing a pinned file leaves its receipts describing bytes the tree no longer
holds. Before changing a file, ask `autonomy/evidence/pins.py` what pins it.

## Checks

Run from the repository root. The source-inspection tools need only the standard
library; the Bazel component gate runs inside the recorded Insula rootfs through
the repository wrapper.

```bash
python3 autonomy/tools/layers.py                  # import layering
python3 autonomy/tools/pins.py status [PATH ...]  # which receipts pin a file
python3 autonomy/tools/pins.py check [--base REV] # source pins a change touches
./bazelw --emit-plan test //autonomy/...          # inspect the Insula command
./bazelw test //autonomy/...                      # default perception tests
```

`./bazelw test //autonomy/...` is the default component entry point. Targets
that need Torch, CUDA or a live-gate mount are excluded from that default and
run only through their explicit GPU or live gates. Use
`./bazelw test --config=cuda //autonomy/...` for the GPU rootfs when the B200
runtime is available.
