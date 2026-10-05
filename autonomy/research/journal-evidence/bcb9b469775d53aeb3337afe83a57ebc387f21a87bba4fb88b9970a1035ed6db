# 42 — Measurement-indexed object failure ledger

Goal: locate the earliest measurable cause of each detection failure, separating missing physical support, absent supervision, geometry/heading error, class ranking and proposal suppression.

Status: approved investigation direction; not implemented or independently admitted.

Reference: compact pillar/dense-GN CNN with clipped Adam; preserve original model/targets/decoder. Parent tickets34/41; source interpretation: `experiments/waymo-perception/research/2026-10-03-initial-experiments-analysis.md`. Oracle interventions are target-side diagnostics, never model observations or learned quality.

Deliverable: one row per native frame/object ID plus versioned linked candidate traces. Record native class, difficulty and evaluation eligibility; positive-point/ROI/training eligibility; originating sensor/return/pixel identities; raw and retained point counts; positive anchor count, best assignment overlap and competing GT IDs; best decoded candidate center/size/3D geometry and heading errors; predicted class/score/rank; survival and rejection reason at score floor, pre-top-k, NMS and post-top-k; final native match where available. Keep native evaluator matching semantics distinct from a proposed geometric diagnostic matching rule. Every row carries frame/object identity, source hashes, checkpoint/head hashes, decoder identity and derivation provenance. Missing/unobservable values are explicit, never fabricated as zero.

Verifiers and acceptance:
- Frozen16 cohort reconciles all1,279 native GT; report all1,053 training-eligible targets and30 uncovered objects without dropping them. Independent reference derives eligibility/coverage and reconciles point identities to original measurements and retention indices.
- Literal independent V3 decode/rank/NMS trace matches retained predictions and native protobuf fields; deterministic ties and every filtering stage have hand-checkable fixtures. Best diagnostic candidate definitions and candidate-to-GT association rules are frozen before interpreting results.
- Native match/heading claims use exact independently audited evaluator semantics or are explicitly marked diagnostic if the evaluator cannot expose a match. No diagnostic IoU match is silently called an official match.
- Live Insula refuses swapped frame/object IDs, dropped GT, reordered point/projection lineage, changed head/decoder hashes and false survival reasons. Every implementation milestone has independently pinned live receipts.
- Camera/LiDAR BEV and perspective views audit representative concrete failure IDs from each observed category; cross-modal correspondence and temporal reference are documented. Save reproducible views and link them to ledger rows, not just scene-level captions.
- Produce a class-by-cause summary and inspect transitions across prescribed checkpoints, including visits/frame. Use the ledger to nominate controlled follow-ups; it does not establish intervention efficacy.
- HDFS exact readback and live recovery preserve ledger, trace and view evidence before declared local release. Respect unchanged storage and compute caps.

Decision: adopt the ledger as a diagnostic tool only after completeness, literal trace and live corruption-refusal gates pass. Model/architecture adoption still requires separately frozen held-out multiseed comparisons.
