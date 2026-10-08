# Perception architecture study

User authorization: 2026-10-02, spec the proposed architecture directions and run them through as part of the existing research goals. Execute natively in the existing isolated tracer worktree. No merge or publication requested.

Goal: identify whether measurement retention, pillar encoding, or BEV spatial processing improves native detection quality and time-to-fit under explicit resource budgets. Deliver independently live Insula-admitted experiment evidence and adopt/reject/needs-more-evidence decisions; fixed-batch diagnostics do not establish heldout benefit.

## Baseline and invariant contract

Reference GN8 BEV backbone with original pillar BN, seed17, 0.25m cells,512² grid,20,000 pillars,32 points/pillar,64 output channels. Same first training frame, all17 native eligible targets, unchanged anchor assignment/loss/heads/decoding, Adam1e-4 betas(.9,.999),eps1e-8,wd0,foreachFalse,clip10. FP32,TF32off,deterministic,2000 updates; checkpoints0,25,50,100,200,300,500,750,1000,1500,2000. Initial shared compatible weights must exactly equal baseline; added modules have seed17 deterministic initialization. GN+pointwise LN remains a measured competing candidate, not a silent replacement baseline. No TensorFlow. Preserve original receipts/failed predictions and fullGT.

Live Insula is mandatory for every implementation milestone: contract fixtures, native optimizer execution, independent loss/timing reconciliation and initial/final checkpoint replay, literal proposal/geometry checks, protobuf reread and native metric replay. Lock runtime/source/input/output hashes. CPU preparations and native CPP metrics use separate existing roots. GPU runs serial. Scientific working cap15GiB, raw2GiB, allocatedGPU8GiB,workerRSS16GiB; per new training run768MiB. Stop a resource-exceeding treatment, retain failure, do not silently retune.

## A: pillar encoding (first cohort)

A1 deep point MLP: append Linear64→64,biasFalse,pointwise LN eps1e-3,ReLU to original point Linear9→64,BN,ReLU; max pooling unchanged. This tests extra pointwise depth without changing the first-layer normalization/padding policy.

A2 contextual encoder: original Linear9→64,BN,ReLU; compute max and mean across valid points, broadcast128-channel summary, concatenate with each64-point feature; Linear192→64,biasFalse,pointwise LN eps1e-3,ReLU; max across valid points. Counts are supplied by wrapper. Masked reduction is intrinsic to contextual aggregation and a declared treatment difference, not a pure depth ablation. Later masked-baseline control is mandatory before attributing gains to context alone. Both outputP×64 and leave scatter/backbone/heads unchanged. No inputGT or label-derived features. Valid point order permutation and evaluation padding-extension invariance are checked; trainingBN includes padded slots, so training padding invariance is not claimed.

Acceptance: live shape/finite/gradient/permutation/context fixtures; same first-projection/backbone/head initial weights; 11-checkpoint audit admission; report per-class native AP/APH, first observed and sustained mean≥.8 and per-class≥.8, brackets in updates/synchronized step wall, loss components, clipping, memory, params. Strong Tier1 remains open absent cyclists or sign failure.

## B: BEV processing (first cohort)

B1 residual CNN: keep original first stride2 convolution and all stage resolutions/widths/upbranches. Wrap each original subsequent Conv3×3+GN8+ReLU unit in identity residual addition: ReLU(x + ReLU(GN(Conv(x)))). This precisely specified minimal residual treatment retains every original weight and parameter count, and is not claimed to reproduce ResNet. No change to detection lattice or features384×256². Test zeroed residual branch acts as identity for nonnegative features and output shape/gradient/native replay.

B2 convolution-window-attention hybrid: later subproject. Preserve fine convolution path; add local spatial attention at coarse stage with metric positions and alternating windows. Specify window widths, channels, masks and compute-matched convolution control before implementation. No global512² attention.

B3 sparse spatial transformer: later subproject anchored on DSVT https://arxiv.org/abs/2301.06051. Requires explicit sparse token/set indexing and separate sparse-backbone interface audit. It is not equivalent to replacing a dense conv with generic ViT.

## C: grouping and retention

C1 32→64 point cap at fixed grid/pillar cap/seed, unchanged encoder. Repack original physical source points; recompute observations, counts and centroids. Keep nativeGT unchanged; independently reconcile retained source indices and all source-point accounting, regenerated positive-anchor/target arrays must equal baseline.

C2 ragged dynamic pillars retain all points within selected pillars; segmented means/max and source mapping. Removing20,000 pillar cap is separate. Test equivalence to fixed packing when neither cap binds, plus permutation/segmented-gradients and exact accounting. Resource failure is a recorded outcome.

C3 cell-size0.125/.25/.5m at same128m ROI. First sweep holds physical head spacing.25×2=.5m and physical anchors fixed; different input/downsample topology explicitly declared. Separate sweep changes head lattice and reruns assignment; no causal attribution to input resolution alone. Reconcile support/truncation/grid boundaries and nativeGT per treatment. Require written per-sweep interface details before GPU execution.

## D: range-view and attention pillar candidates

D1 range→point→pillar features use existing range/pillar prototype with preserved laser/return/row/column/source-index provenance. Verify physical point gather matches stored identities and no semanticGT leaks. D2 within-pillar attention uses relativeXYZ, masked valid tokens and invariant pooling; requires written channel/depth/head and compute-control details before execution. Existing prototype/live probes do not satisfy training/quality admission.

## E: architecture admission and downstream program

First-batch comparisons are diagnostics. Three signs have no positive anchor and fixture lacks cyclists; no variant can receive whole-modelTier1 here. Separate assignment/support control retains allGT and identifies sign localization/coverage issues. A fixture spanning all4 classes, fixed16-frame run, multiple initialization seeds and official segment-disjoint heldout evaluation precede adoption. Candidate combinations only after independent-axis decisions. Detection/segmentation remain separate task contracts; preserve point features/source identity to enable later semantic heads, range/camera fusion and causal Motion comparisons. No claim that detection gain proves segmentation/planning gain.

A treatment is an improvement candidate if it is fully independently admitted and improves final native quality or sampled time-to-quality without a hidden protocol/resource change. Adopt/reject for the research recipe requires broader evidence; inconclusive or failed gates mean needs-more-evidence. Primary and secondary decoder results are distinguished. Score-before-decode secondary is permitted only with exact baseline proposal equivalence retained.

## Sources

Current implementations pipeline/pillar_encoder.py,pillar_detector.py,pillar_packing.py; audited normalization-ablation-results.md. PointNet https://arxiv.org/abs/1612.00593; dynamic voxelization https://proceedings.mlr.press/v100/zhou20a/zhou20a.pdf; DSVT https://arxiv.org/abs/2301.06051. Proposed modules above are adaptations, not reproductions of these papers.
