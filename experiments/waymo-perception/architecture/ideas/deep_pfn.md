# Deeper point MLP

**Experiment ID:** `deep_pfn`

**Status:** runnable

**Goal / hypothesis:** Pointwise nonlinear depth may improve geometry encoding without spatial interactions.

**Configuration:** Append Linear64→64 (no bias), pointwise LayerNorm eps1e-3 and ReLU after the original Linear9→64/BN/ReLU; keep max pooling and64-channel output.

**Attribution limits:** Extra depth retains the original padded BN/max policy; do not attribute gains to masking.

**Verifiers and acceptance:** Every implementation milestone runs live Insula. Preserve original measurements, source indices and all eligible native targets; no label-derived model inputs. Fixed-batch training uses seed17, Adam1e-4, clip10, FP32/deterministic,2,000 updates and11 checkpoint scores. Each run requires contract checks, independent loss/timing and strict checkpoint/Adam replay, literal geometry/NMS/point/NLZ/GT checks, protobuf reread and native metric replay. GPU8GiB,workerRSS16GiB,scientific15GiB,training outputs768MiB. A mean score alone does not pass whole-model Tier1: require per-class quality and all four classes, followed by fixed-cohort/multiple-seed/segment-disjoint heldout evaluation before adoption.

**Observed first-batch result:** mean LEVEL2 APH 0.848343; sign APH 0.545349; 4,851,368 parameters. All11 checkpoint scoring audits admitted. No cyclist coverage; strict sign gate fails. These are training diagnostics, not heldout benefits. See [full comparison](../../research/architecture-first-cohort-results.md).

From the worktree root, run a fresh, isolated experiment:

```bash
python experiments/waymo-perception/architecture.py run deep_pfn --run-id deep_pfn-trial01
```

Verify its retained evidence:

```bash
python experiments/waymo-perception/architecture.py verify deep_pfn --run-id deep_pfn-trial01
```

**Next decision:** do not promote from this batch; needs-more-evidence.

Baseline and shared protocol: [experiment guide](../README.md), [study spec](../../../../docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md), and tickets28–32.
