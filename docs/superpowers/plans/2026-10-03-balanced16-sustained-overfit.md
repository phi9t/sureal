# Balanced16 Sustained Overfit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Continue in the existing isolated worktree.

**Goal:** Establish whether matched detection candidates can sustain native all-class overfit on the admitted sixteen training frames before larger scientific training.

**Architecture:** Preserve the admitted balanced16 physical observations, target assignments and full native GT. Add a separate resumable cohort runner with per-checkpoint replay, literal loss and proposal/export/native metric audits. Keep historical 2,000-update runs immutable; use the corrected V3 decoder in a new namespace.

**Tech Stack:** PyTorch, NumPy, locked GPU/CPU/native metrics Insula runtimes, Waystone HDFS.

**Spec:** ../../research/tasks/34-rare-class-learning-diagnosis.md; ../../research/tasks/07-scientific-protocol.md; ../specs/2026-10-02-perception-cohort-pilot-design.md.

## Global Constraints

- TensorFlow forbidden; observations exclude GT IDs, NLZ, annotation masks and label-derived features.
- Use the exact sixteen admitted balanced training frames; preserve all GT, including uncovered targets. No development/held-out data enters fitting or checkpoint selection.
- Single GPU lock: `~/.cache/waystone/waymo-perception/insula/architecture-experiments.lock`. Do not alter active advanced/pipeline/tier1/gpu sources. Start only after the expanded sweep and its closure finish.
- GPU allocated memory <=8 GiB; process RSS <=16 GiB; scientific unique-inode payload <=15 GiB; raw staging <=2 GiB. Reserve2 GiB for one active cohort case before launch. Do not delete historical cases to obtain space.
- Expanded-case HDFS upload, exact readback, independent live recovery and manifest admission precede releasing their local payloads. Cohort checkpoint/head release obeys the same rule.
- A failed fit is a valid diagnostic outcome, not permission to weaken the gate or claim scientific readiness.

## Frozen comparison contract

Run four one-factor recipes with seed17, exactly the same ordered frame list, deterministic round-robin one-frame updates, Adam lr1e-4/betas(.9,.999)/eps1e-8/no weight decay/foreachFalse and clipping10:

1. Baseline: admitted GN backbone and original loss.
2. Residual BEV: existing residual architecture only; baseline loss/optimizer.
3. Class balancing: baseline architecture plus the exact already admitted tier1 class-balanced positive-focal equation. Keep negative, box and direction equations unchanged. Port the admitted equation, not a new weighting formula.
4. Low prior: baseline architecture/loss with the exact admitted tier1 foreground-prior initialization only.

No combined weighting/prior or geometry treatment in this comparison. Record exact source hashes and treatment parameters in each immutable manifest. Historical decoderV2 results are contextual and must not be treated as a matched control for V3.

Maximum32,000 optimizer updates per case, equivalent to2,000 visits per frame. Maximum7,200 seconds of synchronized training per case; separately report wall time, audit time and resource maxima. A time-censored case remains a failure to establish the fit gate, with the actual update count reported. Do not relabel it as an update-cap result.

Fixed scored update grid:0,1,000,2,000,4,000,8,000,12,000,16,000,24,000,32,000. Upon first all-class pass, schedule one additional confirmation checkpoint exactly1,000 updates later, unless the next fixed checkpoint comes earlier; never exceed the update/time cap. Stop only after two consecutive scored checkpoints pass including terminal, or a finite cap. Time-to-fit is bracketed by the last failing and first passing samples; do not claim unsampled precision.

At every scored checkpoint require exact deterministic head replay on all16 frames, finite full model/Adam state and RNG, restart equivalence, literal class/box/direction losses, independent proposal/export/GT reconciliation and native LEVEL2 APH>=0.8 separately for vehicle/pedestrian/sign/cyclist. Classification scores or loss reduction cannot substitute for this gate. Emit class focal terms, positive scores, clipping frequency, residual errors, native GT/eligible counts and all uncovered IDs. Preserve missing/empty semantics.

## Review Focus

- A changed source/helper must invalidate resumable state, never silently continue.
- Frame-cycle position and RNG must survive restarts without repeating/skipping updates.
- A class missing from a metric result must fail, never disappear from the average.
- HDFS failure must retain local payload and prevent budget-exceeding next work.
- A first passing terminal checkpoint without a second pass must remain unconfirmed.

### Task1: Freeze and validate the cohort execution contract

**Files:** Create `experiments/waymo-perception/cohort/sustained_contract.py` and `cohort/test_sustained_contract.py`; create `research/balanced16-sustained.candidate.json`.

**Interfaces:** `validate_contract(candidate, admitted_frames)` returns the ordered immutable recipe; `next_checkpoint(step, first_pass_step)` determines the predeclared scored sample; `fit_status(samples, terminal_step, stop_reason)` returns sustained/finite-censored/unconfirmed status with class-complete requirements.

- [x] Write failing tests for wrong split, changed frame/hash, duplicate frame, missing native class, nonfinite metric, cap overrun, loss-only success and unconfirmed first terminal pass.
- [x] Implement exact comparison values above; test fixed/confirmation grids and update/time stop reasons.
- [x] Run the complete fixtures inside locked CPU Insula. Independently audit candidate/input/runtime identities and resulting assertions/hash/resource receipt. Commit this contract only after live verification.

### Task2: Implement bounded exact continuation and independent replay

**Files:** Create `cohort/train_sustained.py`, `cohort/replay_sustained.py`, `cohort/run_sustained.py`; reuse original frozen sources without editing historical runners.

**Interfaces:** manifest includes candidate/source/input/runtime hashes, ordered frames, recipe, current update and frame cursor. Checkpoint retains model/Adam/all RNG and manifest hash. Each sampled head bundle contains all16 original frame identities and original target hashes.

- [ ] Fail-first restart fixtures detect changed source/input/recipe/cursor/RNG and missing Adam state. Demonstrate deterministic uninterrupted versus resumed updates and exact heads on a bounded live pilot.
- [ ] Implement source-frozen optimizer loops with synchronized timings, all finite checks, per-class diagnostics, update/time limits and deterministic cursor.
- [ ] Run exact all16 model/head/optimizer replay independently, including literal loss reconstruction. Record separate producer/verifier identities; no self-authored loss assertion alone is admission.
- [ ] Before persistent writes, reserve and check unique-inode storage. Retain two scored checkpoints or archive prior checkpoint/head bundles through the existing independently verified HDFS mechanism. A manifest alone cannot justify deletion.

### Task3: Corrected V3 pooled scoring and sustained-fit admission

**Files:** Create `cohort/score_sustained.py`, `cohort/close_sustained.py`; reuse pinned V3 literal proposal and native metric auditors; add `cohort/test_sustained_admission.py`.

- [ ] Fail-first fixtures reject decoderV2 lineage, missing/extra frame/GT, changed score/heading, missing class, nonfinite score, missing replay and nonconsecutive confirmations.
- [ ] Score all16 frames together through official native accumulation while retaining every GT and original source key. Independently replay literal proposals/export/native metrics at every sample.
- [ ] Bind live receipts to the exact candidate, source/runtime/input/output hashes and resources. Record fit update/time brackets and finite-censor reasons.
- [ ] Fresh-context review the whole increment, fix material findings with live RED→GREEN evidence, then land reviewed code and evidence.

### Task4: Execute matched cases and decide readiness

- [ ] Verify expanded sweep closure and exact HDFS recovery/release first; remeasure budget before each case. Do not restart or stop the active sweep to make room.
- [ ] Run baseline, residual BEV, class balancing and low prior serially under the shared lock to sustained fit or finite cap. No tuning from held-out outcomes.
- [ ] Publish results, exact recipes, all native class curves, time/resource diagnostics and adopt/reject/needs-more-evidence decisions in the tracker/journal; HDFS exact readback and replay preserve checkpoints.
- [ ] Promote only a fully admitted sustained fit to the ticket07 full scientific protocol gate. Held-out comparisons, bootstrap uncertainty and larger-cohort training remain separate required work.

This plan specifies the already requested fitting investigation. It is not an approval to launch scientific training before ticket07 or to overwrite active sweep sources. Implement the isolated contract while the sweep runs; execute GPU continuation only after its closure and storage gates.

## Execution ledger

Task1: complete preparation. Five original unit groups passed live after witnessed missing-module RED. Fresh review identified missing checkpoint-sequence enforcement and premature first-pass gate termination. Both were reproduced as two failing groups, fixed, and all seven groups passed live. The real candidate matches the original16 admitted training identities and payload hashes in a separate live CPU invocation. Receipts: `research/balanced16-sustained-contract-{red-review,green-review}-verified.json` and `balanced16-sustained-candidate-live-verified.json`. No GPU continuation or ticket07 admission is claimed.

Ruling: reserve32,000 updates (2,000 visits per frame) and7,200 synchronized training seconds per case to distinguish inadequate exposure from architecture/loss limitations; an unconfirmed/time-censored outcome cannot satisfy the native fitting gate. If this budget is insufficient, report needs-more-evidence without silently increasing it.
