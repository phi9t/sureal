# 48 — Models/training discovery, retention and closeout

Design milestone: MT-4. Workstream: first-class models and training.

**Goal:** make the scientific model/trainer modules directly usable and verifiable, retain reproducible migration evidence, and land the reviewed work.

**Dependencies:** 47; all 44–47 receipts admitted. Landing ready increments may occur earlier; this ticket audits complete workstream acceptance.

**Spec:** [Models/training design](../../superpowers/specs/2026-10-03-first-class-models-training-design.md).

## Deliverables

- Repository overview points directly to models/layers/backbones, training/losses/state, task specs and live verification commands.
- Clean-directory examples construct/inspect a model, select an existing recipe, run live contracts, train/resume a fixed batch and inspect timed overfit results.
- Migration evidence package binds old/new source closures, input/runtime identities, comparisons, checkpoints, resources and independent acceptance.
- Actual HDFS upload, exact readback and independent live recovery of the retained scientific evidence.
- Research-journal entry records ownership migration, scientific limits, negative/censored results and deferred data/evaluation/analysis work.
- Reviewed, tested commits/PRs land; queue closure links the exact landed revision and evidence.

## Verifiers

- Run the documented scientific package and live verification paths in a clean admitted Insula environment; importing from the repository checkout alone is insufficient.
- Independently reopen all workstream receipts and reconcile their source/input/runtime/output identities; reject missing or mismatched stage evidence.
- Reproduce migration summaries from pinned evidence and verify the journal chain using its existing mechanism.
- Exercise actual HDFS readback and live recovery before any declared local payload release, including existing archive-union admission and storage caps.
- Review the isolated scientific and integration diff, with particular attention to checkpoint compatibility, reference independence and unchanged Surflo imports/checkpoints.

## Acceptance

- The actionable goal in the design is met: models and training are installable, discoverable and exercised through the maintained scientific seam.
- Every implementation milestone has candidate-specific independent live evidence; documentation or a producer `passed` flag alone cannot close it.
- Historical source packages, journal snapshots, artifact hashes and checkpoint bytes are preserved.
- Every retained artifact is recoverable under the existing HDFS/Waystone mechanism; any unretained dependency keeps closeout open.
- Original research tasks remain accurately scoped: migration completion does not close held-out detection, segmentation/SAM, Motion forecasting or planning.

## Closure evidence

Provide the landed commits/PRs, complete migration acceptance index, actual commands/logs/exits, HDFS exact-readback and live-recovery receipts, journal evidence reference and explicit deferred items. Task queue completion is recorded only after these verifiers pass.
