# All occupied pillars in the fixture

**Experiment ID:** `all_pillars`

**Status:** runnable

**Goal / hypothesis:** Pillar truncation may remove all measurements from small objects.

**Configuration:** Keep32 points; raise pillar cap20k→30k, covering all26384 occupied pillars in the current fixed frame.

**Attribution limits:** Only this fixture has all-pillar coverage. Removing the sampling draw changes subsequent seeded point samples; target arrays remain byte-identical.

**Verifiers and acceptance:** Every implementation milestone runs live Insula. Preserve original measurements, source indices and all eligible native targets; no label-derived model inputs. Fixed-batch training uses seed17, Adam1e-4, clip10, FP32/deterministic,2,000 updates and11 checkpoint scores. Each run requires contract checks, independent loss/timing and strict checkpoint/Adam replay, literal geometry/NMS/point/NLZ/GT checks, protobuf reread and native metric replay. GPU8GiB,workerRSS16GiB,scientific15GiB,training outputs768MiB. A mean score alone does not pass whole-model Tier1: require per-class quality and all four classes, followed by fixed-cohort/multiple-seed/segment-disjoint heldout evaluation before adoption.

**Observed first-batch result:** mean LEVEL2 APH 0.830791; sign APH 0.502034; 4,847,144 parameters. All11 checkpoint scoring audits admitted. No cyclist coverage; strict sign gate fails. These are training diagnostics, not heldout benefits. See [full comparison](../../research/architecture-first-cohort-results.md).

From the worktree root, run a fresh, isolated experiment:

```bash
python autonomy/architecture.py run all_pillars --run-id all_pillars-trial01
```

Verify its retained evidence:

```bash
python autonomy/architecture.py verify all_pillars --run-id all_pillars-trial01
```

**Next decision:** do not promote from this batch; needs-more-evidence.

Baseline and shared protocol: [experiment guide](../README.md), [study spec](../../../docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md), and tickets28–32.
