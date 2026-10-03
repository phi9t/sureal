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

Task2: partial preparation. `cohort/sustained_loss.py` ports the admitted all-present weighting exactly and has an independent literal absent-class fixture. Eight native frames lack cyclist positives and two lack pedestrian positives, so the original tier1 assertion cannot be reused unchanged. `cohort/sustained_state.py` preserves immutable model/Adam, frame cursor and Python/NumPy/Torch/CUDA RNG bound to externally trusted identity. CPU19→35 restart is exact across a16-frame boundary. Native GPU/CUDA replay, the actual trainer, controller, storage/export and pooled scoring remain required; Task2 is not complete.

Ruling: extend absent-class positive-focal weights to zero, with the original four-class denominator unchanged. No present-class renormalization or target filtering is introduced. All-present results equal the admitted equation bit-for-bit; zero-positive results equal the reference loss. Cost if wrong: the absent-class loss policy must be rejected/revised from controlled16-frame evidence; no improvement is assumed.

Fresh review of state helpers found Adam tensor aliasing during restore and invalid Torch RNG failing after live mutation. Both failures were witnessed in locked CPU Insula; deepcopy on Adam load and isolated CPU/CUDA generator validation fix them. Five state groups and the combined15 contract/loss/state groups passed live. CUDA branches are implemented but their native device verification remains a later launch gate. Receipts preserve RED/GREEN and exact executed-source/input/runtime/output hashes.

Task2: worker preparation implemented in `cohort/train_sustained.py`, `sustained_loop.py` and `sustained_sources.py`. Stable manifest identity is separate from per-chunk target/checkpoint jobs. Source admission requires every Python file in the frozen pipeline/gpu/tier1/cohort package and mandatory execution helpers, plus equality to an externally admitted runtime lock; the host launcher must still independently verify that rootfs. The worker emits all16 heads and exact model/Adam/RNG state with pre-write reservations. Native GPU execution/replay, controller, export/loss audits and HDFS lifecycle remain open.

Fresh review identified loss of time-censored progress, restoration before rewind refusal, and incomplete source-map acceptance. Live regression RED→GREEN now preserves actual completed steps/time and terminal state, refuses rewind without model/Adam mutation, and rejects empty/incomplete/changed source maps. The full25-group CPU suite passes, including the worker's GPU-only refusal before any input/output. It does not prove nativeGPU execution; no new16-frame training launched.

Ruling: begin no update when remaining synchronized budget is less than max(1 second, twice the largest step measured in this chunk). Record the completed trajectory as time-censored and allow its independent terminal scoring. An unexpectedly long atomic step may exceed7,200 seconds; preserve its actual state/time with `resource_overrun`, forbid resource admission/promotion, and stop immediately. Keeping over-budget time in low-level checkpoint serialization supports honest replay and never increases the approved training budget. Cost if wrong: resource-censored cases remain unpromotable and require a revised, separately recorded execution policy.

Ruling: historical balanced16 used shuffledPCG64 visits. The new preregistered round-robin order applies identically to all four new treatments; historicalV2 curves are context, not an identical trajectory control. Cost if wrong: repeat the matched comparison with a separately specified shuffled schedule; do not infer a treatment effect across the sampler change.

Task2 current preparation: serialized baseline0/19/35 native admission launcher and independent GPU checkpoint/full16head verifier are implemented. The verifier has a separate literal full0→35/restart19→35 loop; CPU preparation matches model/Adam/RNG/cursor exactly. Immutable per-stage inputs preserve command replay. Native GPU execution remains pending expanded closure, verified HDFS release and the two-GiB reservation.

Task3 current preparation: independent NumPy loss worker added after each pilotcheckpoint. Live37 CPU groups and all16 historical baseline2000 nativehead/loss checks pass; three re-pinned corrupt-report probes are refused. Historical data validates the auditor only and does not establish a new V3/sustained execution. Controlled class weighting, per-class gradients/ranking and sustained controller/full scoring/HDFS lifecycle remain open.

Task3 GT scope audit: historical preparation filtered to positive-point trainingROI targets (1,053 of1,279 native boxes). New fullGT helper and V3 exporter preserve all native boxes, including100 positive-point outsideROI and126 zero-point boxes, leaving difficultyNone intact. Live41 CPU groups/full1,279 direct nativefield checks and historicalhead V3 export pass. Native/proposal scoring audits remain open; historicalROI/V2 results are not matched controls. Primary new V3 metrics retain all native GT and use the unchanged all-four-class/two-sample threshold.

Task3 scoring preparation landed: 49 live CPU groups and independent literal full16 V3 proposal/NMS/point-count/NLZ/GT plus every protobuf field/native metric replay pass. Review's foreign-frame and duplicate-GT loopholes were reproduced with re-pinned artifacts and now refused before acceptance. Historical baseline2000 full-native-GT APH remains below the all-class gate; no new training is claimed. Native pilot now wires each immutable chunk through these gates.

Task4 storage progress: all eight expanded case payloads were archived, read back exactly, live rehydrated, globally admitted and locally released through the existing bounded publication mechanism. All 1,264 files / 830,511,030 bytes remain recoverable from the per-case HDFS manifests recorded in the retention index. This freed less than the mandatory two-GiB pilot reserve.

Ruling: apply the same approved HDFS preservation/recovery/release lifecycle to the older independently admitted 16-frame native input cache, keeping historical model cases and the active balanced16 cache intact. Bind all 128 cache files to their original 16 independent admissions, and require a separate live whole-member-union/global-readback verifier before release. The two-GiB reserve and fifteen-GiB total cap remain unchanged. Cost if wrong: original cache-dependent replay must rehydrate the exact archived inputs; no original case bytes or evidence are discarded.

Storage review found missing source bindings for the cache publisher and its host admission/release dependencies. The first cache publication was stopped before release, all128 files were rechecked intact, and its interrupted evidence was retained. The complete host source closure is now snapshotted and checked before every transfer/live stage and release. Three provenance refusal groups plus the previous suite pass in locked live Insula (55 total); actual complete cache publication/release remains required.

Task4 cache storage gate passed: all128 original native-input-cache files (1,040,757,892 bytes) preserved across21 HDFS chunks, exact global readback, independent live full-union recovery with5bad-publication refusals, and cache-only local release. Bound host sources were checked before release. Remeasured scientific payload13,233,305,963 bytes permits the required2GiB reserve. Native baseline0/19/35 admission pilot launched in a new source-frozen namespace; execution is not yet acceptance.

Task2 extended continuation preparation: separate literal chunk reference supports the full32,000-update contract and at most8,000 updates per independent invocation. Live CPU restart47→1000 is exact for complete model/Adam/RNG/cursor, with bad range/cursor refusal and all59 preparation tests passing after witnessed RED. A separately mounted GPU transition worker preserves the original producer source identity, independently reconciles actual step/time records and replays the complete interval before original all16-head/state verification. Fresh review is clean. Native extended GPU execution, sustained controller, rolling HDFS lifecycle and scientific gates remain open.

Native pilot current outcome: confirmed terminal native score35 subprocess timeout at600seconds, after19of21 admitted stages. All35 GPU state/head/independentfull/restart/literal-loss/export/proposal proofs remain intact. Original failed score binaries/log are preserved; no completed pilot or fit admission.

Ruling: recover only the two terminal native scoring stages in a new pinned snapshot, changing their subprocess bound from600 to1800seconds and host stage bound to2100seconds. The original evaluator/configuration, full8000 predictions,1,279 native GT, GPU trajectory and7,200-second training budget stay exact. Official Hungarian matching uses a square matrix of the larger prediction/GT subset and101score thresholds; step35's heavier vehicle prediction composition is a runtime hypothesis. Cost if wrong: another bounded scoring failure remains diagnostic; no proposal filtering, GT removal, metric substitution or unsupported admission. Original frozen sources/failure are retained and recovery needs independent native replay and review.

User ruling (2026-10-03): increase scoring budget substantially. Native scoring and independent native replay now default to14,400seconds each; their host stages use14,700seconds, while nonmetric host stages remain1,800seconds and optimization exposure remains7,200seconds. Current frozen1,800-second recovery is preserved; separate long-bound recovery is available only if needed. No change to predictions, GT, native metric configuration or model inputs.

Controller preparation: pure preregistered scheduling now covers fixed/confirmation grids, actual time-cap terminals and resource-censored failures. Fresh review exposed an early time-cap pass being incorrectly promoted by the original fit helper and throwing in the controller. Dedicated live RED→GREEN fixes both: a passing terminal before the scheduled confirmation remains unconfirmed. Host-timeout wiring also uses the higher native budget. The full preparation suite passes68 tests with fresh review; sustained four-case launcher, extended native replay and HDFS lifecycle remain open.

Pilot storage preparation: externally pinned finalreceipt must bind all21 stage admissions and exact57 checkpoint/head/report/log files before the proven bounded HDFS archive/readback/recovery flow can run. Missing/changed/extra/symlink/failed-stage cases refuse. The original cache archive/host-source/independent-union logic is ported to a pilot-only namespace and source closure; actual publication/release requires final pilot admission and separate live union verification. Live inventory RED→GREEN and all75 preparation tests pass; fresh review is clean. No payload is released at this preparation milestone.

Native execution/recovery admission passed: all21 pilot stages independently reviewed (809distinct hash bindings); terminal score35 completed636.837seconds and separate native metric replay is exact. GPU full0→35 and restart19→35 state/head proofs remain bound to original sources; allclassAPH remains0 on these early samples. A separately mounted new transition worker passes native19→35 fullstate/all16heads (303 reviewed hash bindings) after a retained pre-Python failed mount and `/tmp/verifier` correction. Source-frozen pilot HDFS publication/recovery/release is running under the externally reviewed final SHA. This closes the bounded pilot execution interface, not sustained fitting, extended native intervals, controller or science.
