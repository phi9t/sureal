# 30 — Measure information loss from point caps and spatial resolution

**Goal:** Measure information loss from point caps and spatial resolution.

**Status:** authorized; first-cohort execution in progress where applicable.

**Spec:** [Architecture study](../../../docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md).

**Verifier:** Independent original-point/source-index accounting, unchanged-target checks for cap changes, grid/anchor checks and full training/scoring audits.

**Acceptance criteria:** 64point,ragged and fixed-head-spacing grid comparisons complete; resource failures retained; no input/head-resolution conflation.

All implementation milestones require fresh live Insula receipts, pinned source/runtime/input/output identities and independent retained evidence. Fixed-batch diagnostics do not close heldout/program goals. Bind to ticket07 protocol and ticket10 detection task; baseline receipts remain immutable.

Controls:32→64point cache and20k→30kpillar cache each independently live source/allanchor audited with targetNPZbyteidentity. Source-support diagnostic reveals3signs entirely lost to pillar selection. [All-pillar spec](../../../experiments/waymo-perception/research/architecture-retention-controls-spec.md) declares RNG sample change and scene-specific all-pillar coverage. Ragged and grid controls remain open.

First-cohort diagnostic admission complete: [comparison and evidence](../../../experiments/waymo-perception/research/architecture-first-cohort-results.md). Fullclass/heldout gates and remaining directions are still open; no ticket closure.
