# Masked pillar pooling

**Experiment ID:** `masked_pfn`

**Status:** runnable

**Goal / hypothesis:** Padded slots may distort the pooled representation.

**Configuration:** Keep originalLinear/BN/ReLU; exclude invalid slots only in final maximum.

**Attribution limits:** BN still includes padded slots during training. Evaluation padding-extension invariance is required.

**Verifiers and acceptance:** Every implementation milestone runs live Insula. Preserve original measurements, source indices and all eligible native targets; no label-derived model inputs. Fixed-batch training uses seed17, Adam1e-4, clip10, FP32/deterministic,2,000 updates and11 checkpoint scores. Each run requires contract checks, independent loss/timing and strict checkpoint/Adam replay, literal geometry/NMS/point/NLZ/GT checks, protobuf reread and native metric replay. GPU8GiB,workerRSS16GiB,scientific15GiB,training outputs768MiB. A mean score alone does not pass whole-model Tier1: require per-class quality and all four classes, followed by fixed-cohort/multiple-seed/segment-disjoint heldout evaluation before adoption.

**Observed first-batch result:** mean LEVEL2 APH 0.886386; sign APH 0.660118; 4,847,144 parameters. All11 checkpoint scoring audits admitted. No cyclist coverage; strict sign gate fails. These are training diagnostics, not heldout benefits. See [full comparison](../../research/architecture-first-cohort-results.md).

From the worktree root, run a fresh, isolated experiment:

```bash
python autonomy/architecture.py run masked_pfn --run-id masked_pfn-trial01
```

Verify its retained evidence:

```bash
python autonomy/architecture.py verify masked_pfn --run-id masked_pfn-trial01
```

**Next decision:** carry forward to broader controlled evaluation.

Baseline and shared protocol: [experiment guide](../README.md), [study spec](../../../docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md), and tickets28–32.
