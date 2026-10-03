# 35 — All-class single-batch fitting sweep

Goal: establish which runnable pillar, BEV, normalization and optimization treatments can fit one fixed all-class detection batch, and quantify updates/time required under the same native quality contract.

Scope:15 training treatments plus one nonbinding-pillar-cap equivalence control. The selected training frame contains36vehicles/18pedestrians/14signs/5cyclists,73eligibleGT total, all assigned positive anchors. Keep raw measurements, labels and supervision masks separate. Planned grid, ragged-pillar, range-fusion, point-attention and sparse-transformer ideas remain separate tickets.

Spec: `docs/superpowers/specs/2026-10-02-all-class-single-batch-sweep-design.md`.
Plan: `docs/superpowers/plans/2026-10-02-all-class-single-batch-sweep.md`.
Runner: `experiments/waymo-perception/tier1/run.py`.

Acceptance:
- Freeze selection independently of model outcomes; preserve all73nativeGT and point lineage. No class or difficult object can be dropped to improve the gate.
- Each trained case must reachLEVEL2APH>=0.8 for every class at two consecutive sampled checkpoints including the terminal sample. Stop after verified fit within2000updates; otherwise continue the same Adam trajectory through10000 and record a censored negative if it fails.
- Every implementation milestone runs live Insula. Require explicit norm/module/shared-initial-weight/optimizer contracts; independent literal loss checks; independent proposal/measurement/GT audits; protobuf rereading and official C++ evaluator replay; exact reconstruction of every sampled head and terminal model/Adam/RNG state.
- Quantify sampled update/time-to-fit intervals, clipping and positive/negative loss diagnostics, resources and evaluator overhead. GPU timing is observed on a shared device, not an isolated throughput benchmark.
- Enforce scientific15GiB physical unique-inode payload, raw2GiB, allocatedGPU8GiB and processRSS16GiB. Keep source/input/runtime pins and terminal artifacts. Release only declared new transient artifacts after their audits and exact replay, with release-aware verification; preserve historical bytes.
- Verify initial/terminal inference equality for the nonbinding cap control; report it as an equivalence control rather than another trained winner.
- Produce a complete comparison with explicit negative/execution/resource outcomes. A fitting pass does not close detection/generalization or the broader multimodal research program.

Status: active. Corrected baseline and context encoder have passed fitting and exact replay. Full matrix progress: `experiments/waymo-perception/research/tier1-overfit20261002b-results.json`. Deep encoder's saved500-update trajectory awaits verification recovery after a declared-snapshot empty-directory edge case; all data are retained.

Verifier findings: versioned decoderV3 fixes sign-testing before canonicalizing the raw angle; identical2000-update heads yieldpedestrianAPH .758646→.999529 andsign .714347→.927947 in independently audited native replay. Original baseline trajectory was preserved/rescored, not retrained. A Torch Adam serialization/device-placement comparison was separately repaired and live-regression-tested, retaining exact dtype/shape/value equality. Legacy scores and failed logs remain separate.

## Closure2026-10-02

All15 trained treatments passed sustained native all-class overfit; terminal cap equivalence passed. Final-v4 live Insula closure admitted15 rows and771 receipts. Original results/table/closure/cap bundle uploaded and read back exactly on HDFS. Comparison: experiments/waymo-perception/research/tier1-overfit20261002b-results.md. This closes the fixed-batch sweep only; held-out/full-cohort and expanded tickets36–40 remain open.
