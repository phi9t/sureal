# 33 — Balanced all-class detection fitting

Goal: determine whether the existing GroupNorm baseline or residual-BEV backbone can fit the same 16 native training frames with meaningful coverage of every box class before larger-scale training.

Inputs: frozen balanced 16 selection from 64 training scenes; 16 frames from 13 scenes. Native eligible observations: vehicle 533, pedestrian 255, sign 231, cyclist 34. Covered observations remain a separate count; all 30 uncovered GT observations remain evaluation targets.

Verifier: every input passes live Insula producer/reference physical, label, packing and anchor checks. Every candidate must pass all 16 initial/final head and Adam-state replays, all 48 literal frame/checkpoint loss equations, independent proposal/export audits and native evaluator reruns for checkpoints 0/1000/2000. Compare identical identity order, observations, targets, seed 17 and 2000-update recipe; only BEV architecture differs.

Acceptance: native LEVEL 2 APH>=0.8 separately for every class at both 1000 and 2000, and mean-loss reduction>=80%. Record bracketed time-to-fit, synchronized optimization time, GPU/RSS peaks, evaluation overhead and every failure. A negative scientific result closes the experiment once all audits finish but does not permit larger-training promotion.

Status: both candidates completed training, exact replay and loss checks. Independently audited final metrics fail the class gate; all three checkpoint audits are complete. The experiment is complete with a negative promotion decision. Baseline runbalanced20261002a; residual retrybalanced20261002b. First residual attempt retained after its storage reservation blocked launch. Artifact cap remains 15 GiB; measured retention 14.863838 GiB. Native scores use the same official evaluator in isolated roots, now evaluating checkpoints concurrently; partial superseded serial receipts are retained.

Evidence: research/balanced-study-recovery-20261002.json; candidate quality-parallel-v3 receipts; docs/superpowers/specs/2026-10-02-perception-cohort-pilot-design.md.
