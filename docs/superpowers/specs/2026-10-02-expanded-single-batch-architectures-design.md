# Expanded fixed-batch architecture sweep

User scope: include every planned architecture idea in the fixed-all-class batch overfit investigation. Continue the already frozen sixteen-row sweep independently; never rewrite its source pins or historical receipts.

## Goal and invariants

Implement, live-verify and train the six currently planned ideas. Every trained treatment uses the existing fixed frame with 73 native eligible GT objects across all four classes. No TensorFlow, label-derived inputs, GT pruning, altered anchors, altered decoder, or lower quality threshold. Use Torch, seed17, FP32, deterministic algorithms, TF32off, Adam1e-4, clip10. Decode with admitted v3. Native LEVEL2 APH must be at least0.8 for every class at two consecutive sampled checkpoints including terminal. Extend unchanged to10,000 updates when necessary. Report sampled update/time bounds, inference-versus-training losses, clipping, point retention, parameters and peak resources. No heldout claim.

Run as an additional immutable matrix after current serial GPU sweep, using the same fixture, target hashes and independent loss/native/full-trajectory replay contracts. Existing successful baseline evidence is reused with immutable references; avoid retraining it simply to construct a new table.

## Exact treatments

### Grid fine and coarse

Keep128m XY ROI, Z[-4,6), original physical anchors and256² detection lattice with0.5m head spacing. `grid_fine`: cell0.125m,1024² scatter, first existing3×3 convolution stride4. `grid_coarse`: cell0.5m,256² scatter, first convolution stride1. Original explicit one-cell zero padding remains; later strides2/2 and upsample1/2/4 stay unchanged. Existing compatible convolution, normalization, PFN and head weights are preserved. Repack original physical points at32 points/pillar and20,000 pillars with the pinned packing seed. Independently audit boundary handling, every selected source index, cap losses and object support. Targets/anchors remain byte-identical. Stride topology and cap effects are part of the treatment; this is not an input-resolution-only causal claim.

### Ragged pillars

Retain all eligible points inside the same selected0.25m pillars, keeping20,000 pillar cap separate. Store flat physicalXYZ/intensity, lengths, coordinates and flat source-index lineage, sorted by pillar then source index. Use segmented XYZ means to form original nine-channel decorations; shared Linear9→64, originalBN(eps1e-3,momentum0.01) over valid points only, ReLU, segmented max. ReturnP×64 and reuse dense scatter/backbone/heads. Removing padded BN slots is an explicit co-change. Test equivalence in evaluation when padded-slot pooling cannot win and no point cap binds; additionally test segmented values/gradients, point permutation and exact accounting. A deterministic unsupported reduction is an implementation failure to resolve, never an overfit result.

### Within-pillar attention

Keep original32-slot packing and first shared Linear9→64/BN/ReLU. Add one masked attention block: pointwiseLN eps1e-3, four heads of16 channels, bias-freeQKV64→192 and output64→64; add learned bias-free3→64 projection of cluster-relativeXYZ beforeQ/K. Residual attention, then residualLN/Linear64→128/GELU/Linear128→64, followed by valid-point max pooling. No dropout. Process pillars in fixed chunks of512 to bound attention memory; chunks do not change normalization axes. Test finite gradients, padding exclusion, permutation equivariance and invariant pooling. Add a pointwise-only control with the same width/depth and declared parameter accounting; it cannot establish FLOP matching unless measured.

### Range-to-pillar fusion

Use raw native range/intensity/elongation for all present laser/return pairs; exclude NLZ and labels. Read the original LiDAR component for native H/W and physical channels. Match every reconstructed point using(laser,return,row,column), reconcile native valid masks and intensity against the physical fixture, and preserve retained packed source indices. Keep sensor/return grids separate at their actual dimensions.

Reuse the existing range frontend's32/64/128 U-Net feature blocks and zero angular boundary padding; omit its unused semantic/foreground heads. Share weights across sensors/returns. Gather32 feature channels at exact native pixels, then retained packed indices. Add bias-freeLinear32→64, zero-initialized, to the original PFN's shared Linear9→64 output before original BN/ReLU/pooling. Zero initialization preserves baseline initial heads while permitting detector-loss gradients into range projection, then frontend. This trains detection only; semantic heads and segmentation objectives are separate later research. Test gather/gradient alignment, both returns, empty pixels, no-target leakage, zero-fusion equivalence and sensitivity after projection update. Include a zero-range ablation to separate added computation from range information.

### Sparse BEV transformer

A multiscale occupied-token backbone, not a DSVT reproduction and not dense global attention. Keep original0.25m packing/PFN. Pool occupied2×2 cells with segmented mean to64-channel tokens on256² lattice; linear projections128 and256 channels follow two additional2×2 pooling levels at128² and64². At each level run two sparse attention blocks with tokenwiseLN eps1e-3, four heads, bias-freeQKV/output, residualFFN ratio2/GELU, no dropout, learned2D metric-position projection. Partition occupied tokens by8×8 cells; stable axis sorting and deterministic splitting into sets of at most64; alternate X/Y ordering and shift window origin by4 cells in the second block. Key-padding masks exclude vacant set positions. All tokens are retained exactly once per block. Relative metric centers are observations, not labels.

Scatter each level's tokens only after sparse processing, reuse existing128-channel upsample1/2/4 branches and original384-channel heads. Original dense CNN blocks are replaced; PFN/upsample/head initial weights are shared, new sparse layers initialized deterministically. Audit set membership, shift boundaries, masks, coordinates, gradients, empty cells, hierarchy conservation and final256² flatten order. This changes both representation and backbone; comparisons cannot attribute gains to attention alone.

## Live implementation gates

1. CPU Insula cache producers plus independent scalar/source-index references; immutable source/input hashes, full nativeGT and target equivalence.
2. GPU Insula synthetic and actual-frame forward/backward, head shapes, treatment invariants, initial shared-weight equality, finite gradients and resource preflight. RED missing-module then GREEN implementation. Independent reference checks for segmented reductions, attention sets and range gather.
3. Serial actual-frame optimization, every checkpoint's literal loss/native proposal/export/metric audit and exact model/Adam/RNG/full-head trajectory replay. Preserve failed outputs; report distinct implementation, resource and fitting outcomes.
4. Final live closure requires every frozen row, exact summary-to-receipt equality, all checkpoint loss coverage, source/artifact hashes, declared transient lifecycle and native per-class terminal criterion.

GPU allocated8GiB, workerRSS16GiB, raw2GiB remain hard limits. Scientific unique-inode payload remains15GiB until explicitly changed. Adding six models and necessary controls may exceed remaining scientific headroom while preserving terminal Adam/checkpoints. Perform actual cache/checkpoint reservation before writes; never delete historical evidence, move payload outside accounting, or label a resource rejection as a completed overfit experiment. If15GiB cannot admit all treatments, present measured required additional storage before dependent execution.

## Completion

Each treatment receives a task ticket with cache/model/train/final verifiers and links to evidence. Close implementation only after live contracts; close the fixed-batch investigation only after sustained fit or finite10,000-update censored outcome. Future segmentation, multiseed,16-frame and segment-heldout work stays open. Persist recipes so subsequent runs require selecting an experiment ID, not rewriting scripts.

## User storage steering

User explicitly selected HDFS instead of raising the local cap. Resolve Sureal paths through Waystone layout-profile/storage-prefix. Retained experiment artifacts live under the project checkpoints/runs/artifacts namespaces; local scientific working payload remains15GiB. Verify upload and independent downloaded SHA256/member integrity inside live Insula before releasing any declared new local payload. Persist an immutable archival manifest mapping original logical paths to HDFS URI, size, digest and readback receipt; support bounded verified rehydration for replay. No local release on connectivity/auth/roundtrip failure. Keep historical local evidence untouched; first archive only this new sweep and extension after their verification closes. Credential values must never enter logs or receipts.
