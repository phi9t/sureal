# Sparse spatial transformer

**Experiment ID:** `sparse_bev_transformer`

**Status:** planned

**Goal / hypothesis:** Occupied spatial tokens may support broader context at controlled cost.

**Configuration:** Separate sparse token/set indexing and metric position from detection export; DSVT is a research anchor.

**Attribution limits:** Exact topology and sparse-backbone interface remain to be specified. Do not equate this with generic dense ViT replacement.

**Verifiers and acceptance:** Every implementation milestone runs live Insula. Preserve original measurements, source indices and all eligible native targets; no label-derived model inputs. Fixed-batch training uses seed17, Adam1e-4, clip10, FP32/deterministic,2,000 updates and11 checkpoint scores. Each run requires contract checks, independent loss/timing and strict checkpoint/Adam replay, literal geometry/NMS/point/NLZ/GT checks, protobuf reread and native metric replay. GPU8GiB,workerRSS16GiB,scientific15GiB,training outputs768MiB. A mean score alone does not pass whole-model Tier1: require per-class quality and all four classes, followed by fixed-cohort/multiple-seed/segment-disjoint heldout evaluation before adoption.

**Execution gate:** documented idea only. The runner refuses to execute this ID until its concrete interface, controls and live fixtures are implemented. No training or quality claim exists for this candidate. Freeze the configuration stated above, add the module/cache and verifiers, then register it as runnable.

Baseline and shared protocol: [experiment guide](../README.md), [study spec](../../../../docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md), and tickets28–32.
