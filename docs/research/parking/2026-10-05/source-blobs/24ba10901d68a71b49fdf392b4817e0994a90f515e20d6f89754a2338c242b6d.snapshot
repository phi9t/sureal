# 58.B — Normalization-state preparation

2026-10-05. This preparation identifies the normalization state that the future
[task43 diagnostic](../../../tasks/43-frozen-normalization-diagnostic.md)
must control. It runs no normalization intervention, prediction forward pass,
optimizer, training, native scorer or HDFS operation. It establishes no native
quality rescue and does not close43/50/53.

The candidate is bound to base `b32307da442598e192a9259d29a8650be1134589`.
[Provenance](provenance.json) retains the actual worker thread, reservation and
lead acknowledgment, execution envelope, failed launches and integration limit.
The lead must refresh/recheck this candidate against advancing mainline.

## Exact source and live inventory

The [source pins](source-pins.json) bind the current modules. Ten relevant files
also match both historical runs' retained source and original receipt hashes,
including pillar encoder/detector, normalization and architecture modules;
[archived evidence](archived-evidence.json) records those comparisons. The
[live inventory](inventory.json) lists every normalization module by exact name,
type, epsilon, affine shape, buffer, and pre/post-evaluation mode.

| Fresh source model | Pillar normalization | Dense BEV normalization |
|---|---|---|
| baseline, residual BEV, class-balanced focal, foreground prior | `encoder.norm`: one BN1d, 64 channels | 19 GN modules, 8 groups |
| full BN control | one BN1d, 64 channels | 19 BN2d modules |
| point-LN control | `encoder.norm.norm`: one LN, 64 channels | 19 GN modules, 8 groups |
| no-norm control | Identity | Identity |

These are fresh seed 17 CPU constructions using
[the catalog](../../../../../experiments/waymo-perception/tier1/catalog.py) and
[build seam](../../../../../experiments/waymo-perception/tier1/models.py), without
trained weights. Constructing catalog controls for inspection does not replace
normalization in either archived checkpoint or authorize a treatment.

For the baseline, block0 has four GN64 modules; block1 six GN128; block2 six
GN256; each of three upsamplers has GN128. Residual wrapping changes interior
names to `blocks.<i>.<j>.unit.1`, retaining the same channel/group counts. Exact
names are in the JSON. All normalization epsilon values are `1e-3`.

## Modes, axes and buffer contract

[PillarFeatureNet](../../../../../experiments/waymo-perception/pipeline/pillar_encoder.py)
applies a bias-free 9→64 linear map, then BN to `[pillars,64,point_slots]`.
BN reduces across pillars and point slots for each channel. Decorations mask
padding to zero before the linear map, but BN includes every padded slot; ReLU
is followed by max pooling without remasking. A physical frame batch size of
one therefore does not mean a single BN sample. Pillar/point retention changes
that statistics population.

The retained BN has momentum `.01`, affine weight/bias `[64]`, running mean/var
`[64]` float32, and scalar int64 `num_batches_tracked`; running-statistics tracking
is enabled. In evaluation it uses stored moments. In training it uses current
population moments and updates the three buffers. The installed, pinned Torch
BN source specifies biased variance for current normalization and unbiased
variance for the moving estimate; the update weights are `.99` old and `.01`
current. The pinned library paths/digests are in [inventory.json](inventory.json).

[GN replacement](../../../../../experiments/waymo-perception/gpu/norm_variants.py)
replaces BN2d only for `gn_backbone`, leaving pillar BN intact. GN computes
moments within each example over a channel group and its spatial positions,
using current input in both modes and retaining no running moments. The
point-LN wrapper transposes to `[pillars,point_slots,64]` and normalizes only the
last channel axis per point; it has no running moments. GN/LN affine values
remain learned parameters that task43 must freeze.

Fresh `.eval()` checks changed every module flag to false without changing any
parameter or buffer bytes. Evaluation mode alone does not freeze weights.
Historical checkpoints serialize state dictionaries and RNG/optimizer state,
but no module-mode vector. Their original evaluation mode must be reconstructed
from the producer; a future diagnostic must snapshot and restore each module's
flag, every buffer, parameters and RNG explicitly.

The [historical producer](../../../../../experiments/waymo-perception/cohort/train_balanced.py)
saved evaluation heads, then for each sampled frame cloned all buffers, called
whole-model `.train()` under `no_grad`, computed diagnostic losses, copied every
buffer back and called `.eval()`. That records buffer-restored losses; it does
not retain counterfactual native predictions or task43's complete state/RNG
restoration proof.

## Retained checkpoints and archived measurements

Both historical terminal `checkpoint.pt` files remain locally available:

| Run / terminal step | Checkpoint SHA256 | Manifest SHA256 |
|---|---|---|
| baseline / 2000 | `b412606ca788d83a024d8b9f83d88e3ec133805cb753df61292d8191102974de` | `ab2ffa9c3652c24118ad3f52a0011f7e2895b3f3b82b64b86903dde51f84a675` |
| residual BEV / 2000 | `1ec196c772e6ad887bac515df72f96d017d45425f22e142edea08e86146ffde9` | `1a3cec0652b86d51e997837ba309cf52e648b624e798e8c39ddc5e95e88f3d1f` |

Their exact paths, frame/input pins and five original admissions per run are in
[archived-evidence.json](archived-evidence.json). All51 retained train artifacts
per run were reopened against the train receipt, including all 48 saved head
files for steps 0/1000/2000. The fresh CPU execution decoded only the trusted
state dictionaries with CPU mapping: each has 69 model tensors, exactly the
three pillar BN buffers, counter 2000, optimizer state and Torch/CUDA/sampling
RNG fields. All BN tensor hashes are retained; checkpoint file bytes stayed
unchanged. No trained model or optimizer was restored or executed.

Recomputing sixteen terminal component rows from the actual producer reports
reproduces the [October3 analysis](../../../../../experiments/waymo-perception/research/2026-10-03-initial-experiments-analysis.md):

| Archived terminal mean | Baseline eval / batch-statistics | Residual eval / batch-statistics |
|---|---|---|
| Total loss | 1.073230 / .294972 = **3.638** | 1.266910 / .294760 = **4.298** |
| Localization | .324763 / .049393 = **6.575** | .381633 / .050954 = **7.490** |

These are archived loss ratios, not fresh loss measurements, gradient ratios
or native-quality gains. The baseline's separate V3/full-native-GT metric
receipt remains a distinct historical observation; no matched residual V3
result or modified-buffer native replay is established here.

All 2,000 retained step records confirm 125 visits to each of 16 frames. The
single-frame baseline's first sampled native pass/confirmation occurred at
500/750 visits. Matching those visit counts across 16 frames requires 8,000/12,000
total updates. This is exposure accounting, not a prediction of fitting time
or throughput. Historical seeded permutations differ from the approved
[round-robin loop](../../../../../experiments/waymo-perception/cohort/sustained_loop.py).

The reopened sustained controller status retains baseline checkpoints 0/1000,
with exact checkpoint hashes and all 14 seven-stage receipts across those
samples. Its status is interface admission awaiting review, not a terminal
fitting outcome. No matched terminal sustained matrix is available in that
retained status.

## New execution, limits and next input

[The live receipt](live-verified.json) retains real Bubblewrap argv, exit0,
runtime lock and verified full rootfs digest, mounted-source/input hashes and
artifact hashes. The CPU check took 20.839s including rootfs verification;
the inventory body took 0.960s. The unique systemd scope enforced 2 GiB,
swap 0 and 600s, with no GPU mounts. Process peak RSS was 548720 KiB; sampled
cgroup `memory.current` maximum during child execution was 395161600 bytes;
no OOM event occurred. Kernel `memory.peak` is unavailable, so no exact cgroup
peak is claimed. The three owned scopes are inactive with empty control groups
in [stop evidence](stop-verified.json).

Two failed launches remain in the exclusive external output. Both failed at
creation of `/historical` beneath the read-only root before Python; the first
wrapper also assumed unavailable `memory.peak`. The final launch mounts under
the existing `/tmp` tmpfs and retains supported resource evidence. An early
commentary incorrectly inferred a produced inventory before opening the child
log; it was corrected before acceptance.

Still missing: native predictions/metrics for changed-buffer arms, a declared
recalibration pass/momentum policy, complete per-arm state/mode/RNG equality
receipts, relevant task42 object/proposal traces, and matched terminal sustained
recipes. The named `initial-experiments-evidence-audit.json` does not exist at
this base; the audit Markdown and actual `analysis.json` are pinned instead.
[The next bounded task43 brief](next43.md) specifies how to prepare those
inputs while preserving the four frozen recipes, V3 decoder, round robin and
all 1,279 native GT.
