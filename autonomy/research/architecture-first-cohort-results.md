# Architecture first-cohort results

Eight candidates completed 2,000 updates on the same fixed training frame, with the same seed, optimizer, losses, anchors and all 17 eligible native targets. Each candidate passed separate live Insula loss checks, strict checkpoint replay, and geometry/export/native-metric audits at all 11 sampled checkpoints. The GN-backbone baseline finishes at mean LEVEL2 APH **0.878552**.

| Candidate | Parameters | Final mean APH | First sampled mean ≥0.8 | Training-time bracket | Sign APH |
| --- | ---: | ---: | --- | --- | ---: |
| Deeper point MLP | 4,851,368 | 0.848343 | (200, 300] updates | (13.804, 20.599] s | 0.545349 |
| Contextual pillar encoder | 4,859,560 | 0.857262 | (200, 300] updates | (14.674, 22.101] s | 0.571976 |
| Residual BEV CNN | 4,847,144 | 0.907812 | (200, 300] updates | (14.006, 20.863] s | 0.726450 |
| 64 points per pillar | 4,847,144 | 0.848249 | (200, 300] updates | (15.147, 22.258] s | 0.545297 |
| Masked max pooling | 4,847,144 | 0.886386 | (200, 300] updates | (14.834, 22.549] s | 0.660118 |
| Window attention | 5,109,800 | 0.878419 | (200, 300] updates | (16.620, 23.639] s | 0.636184 |
| Equal-parameter convolution control | 5,109,800 | 0.878573 | (300, 500] updates | (20.487, 33.869] s | 0.636358 |
| All occupied pillars (this frame) | 4,847,144 | 0.830791 | (300, 500] updates | (20.315, 33.777] s | 0.502034 |

Every candidate remains above the mean threshold at all later sampled checkpoints. **None passes the stricter per-class threshold of 0.8**, and this frame contains no cyclists. These results therefore do not pass whole-model Tier1 or establish heldout improvements.

Prioritize the residual CNN and masked-pooling baseline for broader controlled evaluation. The residual CNN improves final quality with the same parameter count as the baseline. Contextual encoding finishes below its masked-pooling control. Window attention and its convolution control finish essentially level with the baseline; each adds 262,656 parameters. They match parameter count, not FLOPs. Extra point-encoder complexity and retention changes are not adopted from this batch.

The 32-point baseline retains 101,303 points. Raising the cap to 64 retains 109,842; removing pillar truncation for this frame retains 133,910. A separate live support diagnostic identifies three sign boxes whose measured points all lie in discarded pillars under the 20,000-pillar cap. Recovering observations alone did not improve fitting under the unchanged recipe. Anchor assignment and thin-sign localization still need investigation.

Training-time brackets use synchronized cumulative step wall time, including transfers and checks, and exclude scoring/replay overhead. CPU work overlapped some GPU runs, so these are engineering observations rather than exclusive whole-machine benchmarks. A scheduler bug allowed an early replay to overlap the original contextual run; an exclusive repeat reproduced all 11 prediction tensors and all 2,000 loss/gradient records exactly. Only the repeat timing appears here. The failed invocation and original evidence are preserved.

Peak allocated GPU memory across these runs was below 2.7 GiB. A live retained-storage audit reconciled 9,095,758,634 bytes under the 15 GiB scientific cap; each training run stayed below 768 MiB of outputs. The resource report does not claim an unmeasured transient storage peak.

An independent code review found no critical model masking or attention-partition defect. Its provenance, residual-weight coverage and storage-gate findings were fixed and tested live, including deliberate corruption/overflow rejection. Strict checkpoint re-admissions verify producer/input/source/driver pins, checkpoint manifest identity, and Adam state shapes and recipe. Final reconciliation verified 1,529 artifact hashes.

Full curves, per-class scores, resources, first/sustained thresholds and receipt hashes: [machine-readable results](architecture-first-cohort-results.json).

The [study spec](../../../docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md), [implementation plan](../../../docs/superpowers/plans/2026-10-02-perception-architecture-study.md), and tickets 28–32 record the remaining work: ragged/grid controls, range and local point attention, sign support/assignment, full-class Tier1, fixed 16-frame fitting, multiple seeds, and official segment-disjoint heldout evaluation. The overall research goals remain open.
