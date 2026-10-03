# All-class single-batch sweep execution

Spec: ../specs/2026-10-02-all-class-single-batch-sweep-design.md

1. Audit all existing content-identical scientific files; deduplicate atomically with preserved paths/bytes and admit unique-inode storage accounting in live Insula.
2. Freeze and independently admit the selected all-class frame, baseline/retain64/all-pillar packing and full native targets. Verify all73GT and source lineage; do not select by model outcomes.
3. Freeze experiment matrix and implement a shared model/recipe seam plus literal loss/replay adaptations. Test norm, architecture weight/gradient contracts and optimizer controls in live Insula.
4. Run each fixed-batch optimizer trajectory serially, retaining checkpoints through native loss/proposal/export/evaluator audits and recording time-to-fit. Extend failed primary runs on the same trajectory to10000max.
5. Independently replay every checkpoint and terminal Adam state before releasing only new transient intermediate heads. Maintain15GiB unique-payload cap; retain historic artifacts and all persistent native curves/terminal evidence.
6. Publish the local experiment comparison and decisions; negatives/resource failures remain explicit. Review the implementation once and close only experiments whose mandatory admissions passed. Planned architecture ideas remain separate pending scope clarification.

Ruling: use one frame that covers all four classes and has no uncovered GT; prior single-frame results with no cyclists cannot certify this new gate. The old16-frame comparison remains unchanged.

2026-10-02 review rulings:
- Preserve the first baseline trajectory and all historical evidence. Supplement its admissions rather than repeat optimization.
- Native quality can stop subsequent trajectories at an earlier sampled checkpoint pair within the 2000-update primary ceiling. Chunk boundaries 300,500,750,1000,1500,2000 allow verified early stopping; failed trajectories extend unchanged to10000.
- Each scientific head/model write reserves its conservative uncompressed maximum before allocating. Native preparation/export stages reserve additional bounded payload. Every stage retains immutable reports/logs; model/head snapshots are explicitly transient, with supersession/release recorded and exact final trajectory replay mandatory.
- Add live module/norm/shared-weight/Adam contracts, cap-equivalent inference and sampled fit/censor aggregation. Recover first-baseline focal/gradient diagnostics by deterministic replay, marking recovery provenance.
- Replay admission correction: Torch's checkpoint `map_location='cuda'` places an originallyCPU Adam step counter onCUDA, whereas the fresh optimizer keeps this scalar onCPU. Compare tensor dtype, shape and exact values across placement; do not weaken any numerical comparison. A live one-step Adam serialization regression proves counter-value equality and rejects changed value/dtype/shape. Preserve the failed replay log; bind a separately frozen comparator-only worker for replay. Resume the existing sweep/source/runtime identities and optimizer trajectories, reusing already admitted native/loss stages. Model training code is unchanged.
