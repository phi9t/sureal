# Coarse BEV window attention

**Experiment ID:** `window_bev`

**Status:** runnable

**Goal / hypothesis:** Learned spatial interactions may improve the coarsest BEV features.

**Configuration:** Append GN8→Fourierposition→qkv1×1→8×8-window attention,4heads×64channels→output1×1→residual addition after stage3.

**Attribution limits:** Compare coarse_mlp; parameter matching is not FLOP matching. No shift, FFN, dropout or global attention.

**Verifiers and acceptance:** Every implementation milestone runs live Insula. Preserve original measurements, source indices and all eligible native targets; no label-derived model inputs. Fixed-batch training uses seed17, Adam1e-4, clip10, FP32/deterministic,2,000 updates and11 checkpoint scores. Each run requires contract checks, independent loss/timing and strict checkpoint/Adam replay, literal geometry/NMS/point/NLZ/GT checks, protobuf reread and native metric replay. GPU8GiB,workerRSS16GiB,scientific15GiB,training outputs768MiB. A mean score alone does not pass whole-model Tier1: require per-class quality and all four classes, followed by fixed-cohort/multiple-seed/segment-disjoint heldout evaluation before adoption.

**Observed first-batch result:** mean LEVEL2 APH 0.878419; sign APH 0.636184; 5,109,800 parameters. All11 checkpoint scoring audits admitted. No cyclist coverage; strict sign gate fails. These are training diagnostics, not heldout benefits. See [full comparison](../../../research/architecture-first-cohort-results.md).

From the worktree root, run a fresh, isolated experiment:

```bash
python autonomy/architecture.py run window_bev --run-id window_bev-trial01
```

Verify its retained evidence:

```bash
python autonomy/architecture.py verify window_bev --run-id window_bev-trial01
```

**Next decision:** do not promote from this batch; needs-more-evidence.

Baseline and shared protocol: [experiment guide](../README.md), [study spec](../../../../docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md), and tickets28–32.
