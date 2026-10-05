# 43 — Frozen-weight balanced16 normalization diagnostic

Goal: determine whether normalization state changes native detection quality on the exact balanced16 observations, separating buffer effects from optimizer learning.

Status: approved investigation priority; no new intervention executed. Does not alter the active four-recipe sustained study.

Motivation: GN backbone retains pillar BN. Historical terminal evaluation/buffer-restored batch-statistics mean total-loss ratios are3.638 baseline and4.298 residual; localization ratios6.575 and7.490. These loss gaps are not demonstrated native quality improvements. Earlier17GT frozen-weight recalibration improved historical meanAPH .738→.864 without optimizer updates, under a different evaluation contract.

Frozen arms, separately bound for each available terminal checkpoint:
- Original evaluation buffers and frozen parameters, control.
- Per-frame batch-statistics counterfactual with exact saved-buffer restoration after each frame. Specify BN module modes, moment reduction/padding population and handling of all other modules; keep inference/reference independently reproducible.
- Training-observation-only recalibration is conditional: freeze pass order/count and BN update/momentum rules before execution; no labels, future observations or held-out inputs enter recalibration. Evaluate all16 heads under resulting buffers, with original parameters unchanged.

Mandatory verifiers and acceptance:
- Pin exact checkpoint/model/optimizer/RNG, sixteen frame identities, physical-feature lineage and input/runtime/source hashes. Record all parameters and BN buffers before/after. Zero optimizer calls/updates; exact parameter equality. Counterfactual restores every buffer and module mode; state/RNG changes are refused or explicitly restored.
- Independent literal normalization fixtures check axes, padding contribution, running moments and epsilon. Each implementation milestone executes live Insula; deliberately changed parameters, missing restored buffer and foreign-frame interventions are rejected independently.
- Use identical V3 decoder and all1,279 native GT, including outsideROI/zero-point targets. Independently export/reread protobufs and replay official native AP/APH for allfour classes. Loss change alone cannot satisfy this ticket's quality question.
- Report per-frame and per-class loss components, proposal/ranking/survival differences, native AP/APH, heading and geometry errors, class exposure and resources. Link changes to ticket42 object IDs/views where available. Historical V2/ROI values are context only.
- Preserve every-class LEVEL2APH>=.8 at two prescribed consecutive checkpoints includingterminal for any fitting promotion; one frozen checkpoint cannot manufacture confirmation. Resource/execution censoring is needs-more-evidence, not a negative efficacy result.
- Exact HDFS retention/readback/live recovery precedes local release; native scoring14400s/host14700s and scientific/GPU/RSS caps remain unchanged.

Follow-up: pillar LN, if warranted by diagnostics, is a separately frozen matched training treatment with identical inputs, weights where shapes permit, sampler, optimizer, decoder, GT and budget. Do not mix normalization replacement with target/grid/loss/architecture changes. Scientific adoption requires segment-held-out multiseed quality/resource comparisons; this diagnostic cannot close segmentation/SAM/forecasting.

Decision: adopt/reject/needs-more-evidence for the normalization-state explanation from native-quality evidence; record any intervention strictly as a frozen-weight diagnostic, not learned-model progress.
