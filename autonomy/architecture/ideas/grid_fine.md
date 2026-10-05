# Fine0.125m grouping

**Experiment ID:** `grid_fine`

**Status:** planned

**Goal / hypothesis:** Finer XY cells may preserve small-object geometry.

**Configuration:** Keep128mROI;1024² input grid; first study preserves physical0.5m detection-head spacing and anchor templates.

**Attribution limits:** Exact downsampling topology is not yet frozen. Track truncation changes; input resolution and head resolution are different experiments.

**Verifiers and acceptance:** Every implementation milestone runs live Insula. Preserve original measurements, source indices and all eligible native targets; no label-derived model inputs. Fixed-batch training uses seed17, Adam1e-4, clip10, FP32/deterministic,2,000 updates and11 checkpoint scores. Each run requires contract checks, independent loss/timing and strict checkpoint/Adam replay, literal geometry/NMS/point/NLZ/GT checks, protobuf reread and native metric replay. GPU8GiB,workerRSS16GiB,scientific15GiB,training outputs768MiB. A mean score alone does not pass whole-model Tier1: require per-class quality and all four classes, followed by fixed-cohort/multiple-seed/segment-disjoint heldout evaluation before adoption.

**Execution gate:** documented idea only. The runner refuses to execute this ID until its concrete interface, controls and live fixtures are implemented. No training or quality claim exists for this candidate. Freeze the configuration stated above, add the module/cache and verifiers, then register it as runnable.

Baseline and shared protocol: [experiment guide](../README.md), [study spec](../../../../docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md), and tickets28–32.
