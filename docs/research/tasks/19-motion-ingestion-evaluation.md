# 19 — Verify Motion ingestion and forecasting evaluator

**Goal / what to deliver:** Provide causal native Motion examples and benchmark-compatible TF-free forecasting scoring.

**Blocked by:** [06](06-r0-closeout.md)

**Status:** preparing — separate locked native runtime/regressions, acquired training/validation inventories, native causal sensor linkage, camera-codebook features and oracle metric handoff verified live; decoded LiDAR geometry and scientific forecasting protocol/comparisons remain open

**Lane:** core

**Verifier:** Live ingestion of Scenario plus supported extensions; independent source/scenario/time reconciliation, deliberate future-leak rejection and hand-checkable metric fixtures.

## Acceptance criteria

- [ ] Source versions, scenario IDs, current indices, native target tracks and extension availability are recorded.
- [ ] No Perception-to-Motion heuristic join; camera tokens are not represented as raw RGB.
- [ ] Future-state target access is separated from observations; injected future feature fails validation.
- [ ] Pinned horizon/K/class/target/probability configuration and TF-free evaluator parity pass; otherwise downstream scoring remains blocked.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

## Native regression preparation

[Verified native regressions](../../../experiments/waymo-perception/research/motion-native-regressions-verified.json) record 19 Motion metric and 23 utility tests, all run without skips/failures in a separate content-locked offline Insula runtime; dependency checks prove TensorFlow absent. [Source contract](../../../experiments/waymo-perception/research/motion-native-evaluator-contract.md) specifies interfaces, mode ordering, confidence/validity semantics and required analytic fixtures. Existing Perception metric runtime is preserved. This evidence does not close the ticket: native CLI/export parity, acquired source/scenario reconciliation and deliberate causal-leak rejection are still required.

## Additional analytic boundary evidence

[Expanded CLI fixtures](../../../experiments/waymo-perception/research/motion-cli-expanded-verified.json) verify single-scenario errors, missing-label measurement counts, serialized K, confidence mAP and malformed/nonfinite refusal. [Joint-mode fixtures](../../../experiments/waymo-perception/research/motion-joint-verified.json) independently verify that agent errors are averaged within one shared mode before selecting the best mode, with incompatible joint target sets rejected. These live results do not close pooled scoring, interaction/overlap parity, native source ingestion or causal leak checks.

## Ingestion source preparation and next execution gates

[Motion ingestion source contract](../../../experiments/waymo-perception/research/motion-ingestion-source-contract.md) records the paired v1.2.1 release candidate, exact bounded TFRecord CRC32C framing, pinned protobuf schema, historical/current sensor indexing and camera-codebook provenance requirements. The pinned Scenario schema was independently inspected locally: fields 12/13 explicitly correspond to timestamps at indices no later than current_time_index. This is source-contract evidence, not an acquired-object or causal-input receipt.

Execute these gates in order:

1. Resolve actual GCS child paths through authenticated metadata listing; retain release, complete object names, generation, byte size, checksums and compression. Anonymous listing returned HTTP 401; guessed child paths cannot enter an acquisition manifest. Use existing authorized credentials without exposing them. Metadata listing may run independently; raw acquisition must respect the shared staging lease and cap.
2. Prove the TF-free bounded record reader live against known CRC32C vectors, multiple records and empty streams. Independently construct frames; reject altered length/payload checksums, truncated headers/payloads and declared sizes above the configured cap. Record offsets and payload hashes. Outer compression needs observed source evidence and explicit support.
3. Decode acquired Scenario and extensions with pinned protobuf descriptors. Reconcile scenario_id through manifest/filename/native fields, reject duplicate augmentation, reconcile timestamp counts, and retain source hashes. Extension-only records need not populate base track fields.
4. Produce a separate causal model-input projection. Reject any state, signal or sensor index beyond current_time_index; keep immutable full truth exclusively on the scoring side. Deliberate future-state and future-sensor injections must fail live, including scenarios with missing extensions.
5. Score actual acquired scenarios through the locked native CLI; then prove pooled scoring and interaction/overlap fixtures. Report measurement counts so unlabeled cases cannot appear as perfect scores. Close this ticket only after all acceptance criteria and independent receipts pass.

Neither the source-contract note nor synthetic framing fixtures can substitute for native ingestion. The proposed small pilot is preparation for the eventual frozen forecasting cohort, not a replacement for the program's held-out comparisons.

## Authenticated metadata follow-up

The existing isolated GCS credentials successfully listed v1.2.1 metadata. [Bounded authenticated listing evidence](../../../experiments/waymo-perception/research/motion-authenticated-metadata.json) records eight successful Objects:list responses, source generations, sizes and checksums without credentials or payload downloads. Confirmed prefixes: `uncompressed/scenario/{training,validation}/` and `uncompressed/lidar_and_camera/{training,validation}/`. Scenario objects are sharded (observed first training shard448,622,357 bytes and first validation shard273,686,917 bytes); sensor extension objects are per-scenario `{scenario_id}.tfrecord` (observed samples approximately4.5–6.2MB). Listings under split prefixes are intentionally bounded to three objects, have pagination tokens, and are not a complete inventory or frozen scientific cohort. Filename alone does not prove compression. Earlier anonymous401 and unverified-prefix findings remain historical observations; authenticated source-path discovery is now resolved for these exact prefixes. Native ingestion/linkage/causality remain unproved. No shared staging lease was taken.

## TF-free record framing preparation verified

[Live record-reader evidence](../../../experiments/waymo-perception/research/tfrecord-reader-verified.json) records four independent analytical test groups inside the locked CPU Insula after an observed missing-module failure. A bit-at-a-time CRC32C fixture independently constructs envelopes; the candidate uses a lookup table. Known CRC32C vector123456789, mask rotation, empty/multiple records, exact offsets/hashes, short reads, length/payload checksum faults, every truncation boundary and oversized advertised lengths pass required assertions. Positive caller byte caps are mandatory and checked before payload reads. Clean EOF is only accepted between records. A later corrupt record raises; callers must not promote partially yielded records as a complete file.

This closes synthetic uncompressed framing preparation only. Actual object compression, protobuf descriptor identity, source reconciliation, causal projection, native scoring and scientific cohort remain open.

### Native causal projection preparation

Live missing-binary failure observed, then native C++ projection compiled against locked pinned protobuf library without runtime mutation. Separate protoc-built/decode-checked fixtures passed four groups: full future truth stays unchanged while model input excludes future states/signals and target/interaction metadata; injected future sensor coverage rejected; invalid timeline/identity rejected; complete current/history sensor counts preserved. Initial checker substring also counted dynamic-map states; corrected field-specific count and retained failed log. Evidence `research/motion-causal-projection-verified.json` (under experiments/waymo-perception). This is analytic native boundary evidence, not source provenance, sensor contents/geometry, acquired ingestion or held-out forecasting. Ticket19 remains open.

Current causal projection admission uses [schema rejection evidence](../../../experiments/waymo-perception/research/motion-causal-projection-schema-verified.json), superseding the earlier candidate-specific projection receipt. Recursive unknown-field injection reproduced a gap and now fails live before output; five native fixture groups pass. Unknown newer-release fields require explicit schema migration. Acquired native data and scientific comparison gates remain open.

## Complete Scenario source inventory and acquisition pilot candidate

[Motion Scenario metadata inventory](../../../experiments/waymo-perception/research/motion-scenario-inventory.json) exhausted authenticated pagination for1,000training and150validation native Scenario objects, retaining source generations/checksums/sizes and distinct official splits. [Bounded pilot source candidate](../../../experiments/waymo-perception/research/motion-source-pilot.candidate.json) pins deterministic first-name-per-split sources under the existing947,329,295-byte single-source raw allowance. This is metadata/source planning, not acquireddata, an extensioninventory, scientificcohortfreeze or nativeingestion evidence. Acquire only through sharedstaging/HDFS generationpin and readback; allscenario identity/extension/timing/causal/scoring gates remain open. No full research scope is replaced by the pilot.

[Native Motion source pilot plan](../../../docs/superpowers/plans/2026-09-30-motion-native-source-pilot.md) makes acquisition/readback, complete-file CRC/protobuf admission, exact scenario-extension matching, native causal fault injection and scoring handoff concrete. It preserves the full later forecasting study and does not authorize overlapping raw staging.

Pooled scoring preparation: research/motion-pooled-cli-initial-verified.json records a separate native pooled CLI compiled and executed in content-locked TF-free Insula. Two analytic scenarios yield pooled minFDE10 with2 measurements and pooled mAP0.25, rather than the0.5 mean of their individual APs. Native per-scenario sufficient statistics are accumulated before metric computation, following the pinned upstream implementation. Duplicate/missing scenario and broader pooled/interaction parity still require verification; actual ingestion remains open. The original single-scenario runtime/binary is preserved.

Expanded pooled analytic evidence: research/motion-pooled-cli-weighted-verified.json records4 live groups. Duplicate scenario IDs, missing pair files, extra pair columns and empty catalogs refuse output. Unlabeled futures contribute zero measurements and cannot dilute error. Unequal target support (two perfect agents versus one3m-offset agent) yields pooled minADE/minFDE1m with3 measurements, rather than the1.5m mean of scene errors. Full cohort catalog reconciliation and native interaction/overlap parity remain open.

Pooled overlap evidence: research/motion-pooled-cli-mode-overlap-verified.json records6 live pooled groups. A predicted box coinciding with another agent future box versus a clearly separated case yields overlap0.5 with2 measurements. With a correct low-confidence mode and colliding high-confidence mode, minFDE remains0 while overlap is1; reversing confidence makes overlap0. This verifies most-confident-mode collision diagnostics separately from best-of-K displacement. It is analytic fixture evidence, not planning safety validation or acquired-scenario parity.

## Native training source acquired and inventoried (2026-10-02)

The generation-pinned448,622,357-byte training pilot shard matches GCS size/MD5 and exact HDFS SHA readback. The [acquisition receipt](../../../experiments/waymo-perception/research/motion-training-source-acquired.json) records the combined raw peak1,804,558,739 bytes, below2GiB. Separate locked live Python framing and C++ CRC/protobuf invocations each inventory492 records covering the complete source. [Reconciliation](../../../experiments/waymo-perception/research/motion-training-inventory-reconciliation.json) matches every index/offset/length and selected native payload hash. Lowest native ID101d4e5775093d0c has91 timestamps,current index10,62 tracks and2 prediction targets; the base shard has no sensor extensions for this example. Exact corresponding extension metadata is resolved, but extension acquisition/content linkage, causal-input native verification, real-source metric handoff and validation-source ingestion remain open. No forecasting model has trained.

## Native selected extension and causal prefix (2026-10-02)

The5,081,750-byte matching extension passed generation-pinned GCS size/MD5 and exact HDFS SHA readback. [Separate live linkage/projection/check receipt](../../../experiments/waymo-perception/research/motion-training-native-link-verified.json) verifies11 historical/current LiDAR and camera-token frames, eight camera streams per frame,256 tokens per stream,22,528 tokens total and observed codebook indices1–8191. The independently parsed causal output preserves exact native history states/signals/maps and sensor messages, with no future track states or prediction-target/interest fields. Wrong external scenario key, duplicate augmentation and an injected12th sensor frame all fail without output.

**Contract correction:** the real extension has only fields12/13 and no native scenario ID. The pinned [official LiDAR tutorial](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/tutorial/tutorial_womd_lidar.ipynb) and [camera tutorial](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/tutorial/tutorial_womd_camera.ipynb) specify filename-based correspondence. Bind the authenticated full source filename and generation/hash to the base native ID; require matching IDs when a payload supplies one, never invent a missing payload ID. The earlier planned native-ID equality check is superseded by this source-backed rule. Camera support must follow the native Motion stream inventory, not the Perception five-camera count.

Failed probe directoriesv1–v4 are retained separately; v5 alone is admitted. Codebook metadata is resolved, but codebook content/index validation, decoded LiDAR geometry, validation-source ingestion and actual-source metric handoff remain open. This example does not close ticket19 or establish forecasting quality.

## Native camera codebook features (2026-10-02)

The supplied camera codebook is pinned to upstream commit99a4cb3, verified against Git blob64c90db81db83813c03106a3824c10d2058135e0, and mirrored/read back exactly on HDFS. [Live receipt](../../../experiments/waymo-perception/research/motion-codebook-live-verified.json) uses only the admitted historical observations and codebook in its input mounts. Native token extraction and a separate NumPy lookup check preserve22528 unique frame/camera/token-position keys, validate all indices against8192 codebook rows, and produce22528×32 finite float32 features. Literal row lookup matches exactly; negative, oversized and noninteger indices fail. The input observation SHA equals the earlier independently checked causal projection output. No raw RGB is recovered or claimed.

The codebook stage's live Python peakRSS is53,180KiB and feature checking time0.135s; this excludes acquisition and native compilation and is not forecasting inference cost. Decoded LiDAR geometry, validation source, real-source metric handoff and scientific forecast training/comparisons remain open.

## Separate validation source inventory (2026-10-02)

The273,686,917-byte validation shard passed generation-pinned GCS size/MD5 and exact HDFS readback. Independent live Python and native C++ inventories reconcile287 records and complete source bytes. [Validation reconciliation](../../../experiments/waymo-perception/research/motion-validation-inventory-reconciliation.json) records every offset/length match and the bytewise lowest native ID11818a3a928aaefa with its exact payload hash. Current unique raw/protobuf storage remains below2GiB. Validation extension linkage, causal projection and native metric handoff remain open; the two pilot shards are not a frozen scientific forecasting cohort.

## Bounded raw retention

The fully inventoried training pilot shard was locally released after its original source integrity, complete independent live framing/protobuf inventories and exact HDFS readback. A second bounded HDFS download reproduced all448,622,357 bytes and the pinned SHA exactly before its temporary recovery copy was released. [Release receipt](../../../experiments/waymo-perception/research/motion-training-raw-release-verified.json) records recovery URI/command and immutable parent hashes. Selected native truth and causal observations remain local; future full-shard replay must rehydrate from HDFS rather than assume the original raw path exists. Original acquisition/inventory receipts are preserved.

## Validation causal camera path and real native metric handoff (2026-10-03)

The exact validation extension11818a3a928aaefa passed source integrity/HDFS readback, native filename-key linkage and separate causal-prefix validation. Wrong key, duplicate augmentation and future12th sensor frame refuse without output. [Validation camera codebook receipt](../../../experiments/waymo-perception/research/motion-validation-codebook-live-verified.json) separately validates22528 token indices/features on observation-only mounts; its input SHA matches the independently checked validation causal output.

[Acquired-source metric handoff](../../../experiments/waymo-perception/research/motion-real-metric-handoff-verified.json) runs oracle offset0/2m predictions on native training and validation target identities through the pinned TF-free scorer. A separate native parser derives Euclidean errors and measurement counts directly from the retained native truth and serialized predictions; another live checker reconciles all four comparisons at1e-3m tolerance and rejects8 corrupted score/count copies. Training supports one vehicle and one pedestrian; validation supports8 vehicle ADE measurements but only6 FDE measurements due missing endpoints. Missing future labels are not counted as perfect predictions.

These are explicit oracle scoring diagnostics, not causal predictor outputs or a trained forecasting baseline. Configuration is K1,10Hz native history/future,2Hz predictions,16 predicted steps and measurement endpoint15 with lateral/longitudinal thresholds3/6m. Other horizons/classes and pooled behavior retain their separate analytic evidence; these examples do not certify full scientific-cohort parity. Decoded native LiDAR geometry and the forecasting cohort/protocol/model comparisons remain open. Failed metric fixture compilationv1 is retained; admitted producer invocationv2 and independent reference/check invocations are separate.
