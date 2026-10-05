# Architecture

How the experiment's code is arranged, what may depend on what, and which
bytes are frozen. The three rules below are checked by `tools/`, so this file
describes them; it does not enforce them.

## Layers

Each top-level directory is an *area*. An area may import its own modules and
any area on a lower row. Areas on the same row are peers and do not import each
other. The order is declared in [`tools/layers.py`](tools/layers.py).

| Layer | Areas | Role |
| --- | --- | --- |
| 9 | top-level scripts, `scripts/`, `analysis/`, `tests/`, `tools/` | Gate runners, operations, diagnostics, development checks |
| 8 | `continuation_control/` | Binds bounded legacy replays to their native receipts |
| 7 | `continuation/` | Parity checks for resumed native stages |
| 6 | `resources/` | Measured, cgroup-bounded stage execution and retention |
| 5 | `cohort/` | 16-scene cohort studies: balanced and sustained training, scoring, audits |
| 4 | `advanced/` | Expanded fixed-batch architecture suite |
| 3 | `tier1/` | Fixed-batch architecture overfit suite |
| 2 | `architecture/` | Experiment catalog and the `architecture.py` runner |
| 1 | `gpu/`, `evaluation/`, `tracking/`, `association/`, `explorer/`, `motion-evaluation/`, `viewer/` | Model variants and GPU workers, native metric contracts, journal, standalone tools |
| 0 | `pipeline/` | Readers, geometry, encoders, detector, archives, Insula entry; imports no other area |

`research/` holds retained evidence, including frozen copies of sources, and is
outside the layering.

One upward import exists: `tier1/prepare_v3.py` imports `cohort/balanced.py`.
It is listed as the only entry of `KNOWN_UPWARD`.

Cross-area imports are qualified (`from pipeline.geometry import ...`). A bare
import (`import models`) resolves through whichever directories a script put on
`sys.path`, and 14 module names (`models`, `catalog`, `train`, `prepare`, ...)
exist in more than one area. The check refuses a bare import whose name is
defined by more than one other area.

## Two kinds of source

- **Library code** is imported by other modules: most of `pipeline/`, the model
  and variant modules in `gpu/`, `tier1/` and `advanced/`, the stage backend in
  `resources/`, the journal in `tracking/`.
- **Procedure records** are scripts that ran one gate or one study stage and
  wrote a receipt containing their own digest: the top-level `verify-*.py` and
  `publish-*.py`, the hyphenated workers in `gpu/` and `cohort/`, and the
  `_v2`/`_v3` successors beside them.

Both kinds are cited by receipts. Almost every tracked file outside
`research/` has the SHA-256 of its current bytes recorded in at least one
retained receipt (`tools/pins.py status` prints the count per area). Two
validators also require an exact file inventory, so adding a file there changes
what they admit:

- `cohort/sustained_sources.py`: every `*.py` under `pipeline/`, `gpu/`,
  `tier1/` and `cohort/`, which `cohort/sustained_controller_backend.py`
  freezes for each sustained run;
- `resources/sources.py`: every `*.py` under `resources/`.

This is why a changed procedure appears as a new `_v2` file instead of an edit:
editing a cited file leaves its receipts describing bytes the tree no longer
holds. Before changing a file, ask `tools/pins.py` what cites it.

## Checks

Run from this directory. The tools need only the standard library.

```bash
python3 tools/layers.py                  # import layering
python3 tools/pins.py status [PATH ...]  # which receipts cite a file
python3 tools/pins.py check [--base REV] # cited files a change touches
PYTHON tools/suites.py [AREA ...] -j 8   # every unit-test module
```

`suites.py` runs each test module in its own process and reports a module as
*unavailable*, not failed, when it stops only on a missing third-party package
or a missing sandbox mount. Use an interpreter with NumPy and PyArrow for
`PYTHON`, for example the tracer environment
(`~/.cache/waystone/waymo-perception/probe-venv/bin/python`). Torch exists only
inside the GPU root and paths such as `/experiment` and `/outputs` only inside
Insula, so those modules run under their live gates.
