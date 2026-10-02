# 29 — Compare residual convolution and windowed attention for BEV reasoning

**Goal:** Compare residual convolution and windowed attention for BEV reasoning.

**Status:** authorized; first-cohort execution in progress where applicable.

**Spec:** [Architecture study](../../../docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md).

**Verifier:** Live shape/residual-zero/window-index/mask fixtures plus native quality/time/resources audits.

**Acceptance criteria:** Residual first cohort admitted; attention exact interface and compute-matched control specified and audited before comparison.

All implementation milestones require fresh live Insula receipts, pinned source/runtime/input/output identities and independent retained evidence. Fixed-batch diagnostics do not close heldout/program goals. Bind to ticket07 protocol and ticket10 detection task; baseline receipts remain immutable.

First-cohort implementation: minimal residualBEV; coarse8×8windowattention4heads with Fourierposition; equal-added-parameter coarseMLP control. Concrete [followup spec](../../../experiments/waymo-perception/research/architecture-window-control-spec.md). Parameter matching is not FLOP matching; report measured resources. Native scoring/audits and strict receipt reconciliation required before result admission.

First-cohort diagnostic admission complete: [comparison and evidence](../../../experiments/waymo-perception/research/architecture-first-cohort-results.md). Fullclass/heldout gates and remaining directions are still open; no ticket closure.
