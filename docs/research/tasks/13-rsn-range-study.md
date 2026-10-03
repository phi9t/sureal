# 13 — Evaluate the RSN range-view pathway

**Goal / what to deliver:** Determine whether range-view processing and foreground selection improve efficient detection without sacrificing recall/support.

**Blocked by:** [10](10-pointpillars-detection.md)

**Status:** planned — blocked by prerequisite verification

**Lane:** core

**Verifier:** Live range-frontend and detector comparisons with independent valid-ray, foreground-recall and retained-background checks.

## Acceptance criteria

- [ ] Declare sensor/return selection; compare it against the same selection in the control.
- [ ] Separate range features from selection by ablation; report selection recall by class/distance and its error ceiling.
- [ ] A full-support branch retains background geometry; RSN selection is not presented as full-scene semantic segmentation.
- [ ] Report AP/APH and end-to-end compute/memory at matched budgets, including frontend costs.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

### Native grid metadata gate

Inspection found scientific point archives preserve sensor/return/pixel identity and range/intensity/elongation but omit native H×W dimensions. Do not infer grid extent from positive-return pixel maxima: empty trailing rows/columns would alter angular geometry. `research/native-range-shapes-verified.json` records live recovery of all3,970 sensor/return shapes for both source-pinned engineering scenes, preserving null shapes. Before scientific range frontend execution, separately replay native shape metadata for all103 original scenes under the shared acquisition leases and link it to each archive/source identity. Existing pinned cohort workers remain unchanged. This is an ingestion gate, not an RSN accuracy result.

Range adapter preparation: `research/native-range-grid-verified.json` records three live Insula fixture groups for explicit native dimensions, original point-order round trips, missing versus undefined semantic labels, unassigned instance IDs, and invalid/duplicate pixel refusal. Range/intensity/elongation are the only measurement channels; NLZ stays outside model input. Full valid-point support is preserved independently of any future foreground gate. Native engineering integration and complete scientific shape-source admission remain required.

Complete native engineering integration: `research/native-range-grid-integration-verified.json` records live point→range→point round trips for all3,970 sensor/return records and71,891,534 points across both engineering scenes. Exact physical-feature and original-index identity, invalid-pixel masks, and all120 annotated returns were checked;9,204,259 eligible semantic points retain support. Worker elapsed72.635s and peakRSS85,804KiB. Retained receipt/artifact hashes independently agree. This accepts adapter integration only; scientific103 source-linked dimensions, trained frontend and controlled comparisons remain open.

Candidate full-support Torch range frontend: `research/range-frontend-verified.json` records three live Insula fixture groups: odd-grid shape restoration, finite backward for all parameters, invalid measurement exclusion, and separate23-class semantic/one-channel foreground heads. Candidate widths32/64/128, GroupNorm, bilinear resizing and zero angular padding are explicit SUREAL choices, not faithful RSN. Every valid pixel retains semantic output independent of future foreground selection. Raw range/intensity/elongation alone enter the encoder. Zero optimizer updates; native GPU integration, matched TOP/return controls and scientific architecture/protocol freeze remain open.

Native GPU range pilot: `research/range-frontend-native-independent-verified.json` links the live GPU result to independently checked source hashes, native pixels and literal semantic-support counts. TOP both returns,2×64×2650 grids,157,870 gathered point features and152,773 eligible semantic elements. Native semantic loss plus a synthetic foreground-square term exercised finite backward; zero optimizer steps. Measured frontend forward/backward0.842s, gather0.00167s, peak allocated2,479,648,768B. This accepts engineering integration only; no trained foreground gate or held-out accuracy claim.

Foreground-support preparation: `research/foreground-support-verified.json` records three live fixture groups for upright oriented box membership, overlapping coarse native box classes, original-point selection recall, and explicit objects-without-observed-support denominators. Selection diagnostics distinguish at-least-one from explicit minimum-point retention. Box membership never replaces native semantic targets; absent class recall remains null. No trained gate, native scalar parity, distance-stratified results or scientific threshold adoption yet.

Native foreground geometry parity: `research/foreground-native-verified.json` records complete independent scalar world-polygon/height checks for157,870 TOP/both-return points against all81 native boxes in the annotated engineering frame. Every per-object point-index set agrees with the vectorized inverse-heading implementation. All-points, no-points and oracle-box-union controls satisfy expected support recall, with unsupported objects kept explicit. Receipt and retained artifact hashes agree. This verifies geometry/diagnostic plumbing only; trained selection, distance-stratified comparisons and scientific threshold adoption remain open.

Point-to-pillar feature seam: `research/packed-point-features-verified.json` records two live Insula groups for exact retained-source feature ordering, zero padding and gradient support only on retained points. Forged/duplicate/out-of-range source indices and count/padding mismatches are refused. No second voxelization changes point membership. Complete native range-feature detector integration and common-head scientific comparisons remain open.

Shared-head hybrid preparation: `research/range-pillar-hybrid-verified.json` records three live Insula fixtures. Extracted shared anchor heads reuse the original modules and exactly match original PointPillars predictions for identical pillar features. The candidate9+32-channel augmented PFN retains64 output channels, source BN/max policy, zero padded range features and finite backward. This prepares an anchor-head engineering hybrid; the program's center-head control and compatible final scientific head freeze remain separate requirements. Native end-to-end GPU execution is pending.

Complete native ungated hybrid: `research/range-pillar-native-independent-verified.json` records live TOP/both-return range→point→original packing→9+32 PFN→shared anchor-head forward/backward. All157,870 points retain semantic/range features;12,342 pillars retain67,999 detector points. Independent native accounting verified1,802 points outside ROI and88,069 dropped by the32-point pillar cap, with no foreground gate and no pillar-count cap loss. Head outputs131,072 anchors. Native semantic loss and synthetic head objectives produce finite gradients throughout; zero optimizer steps. Full hybrid forward/backward0.946s, peak allocated2,642,208,768B. Engineering caps/anchor head remain candidates; TOP/last-return matched scientific controls, center-head control, training and held-out comparisons remain open.

### Full-cohort native range dimensions: execution prerequisite

The original scientific point archives omit native H×W×4 dimensions. Deriving
extent from positive point pixels loses empty edge pixels and is inadmissible for
range-view input. The original103-scene source inventory and live admission are
recorded in `research/scientific-native-range-shape-sources.candidate.json` and
`research/scientific-native-shape-inventory-verified.json` (experiment-relative).
Expected return records203,850; total serial raw readback17,382,154,779bytes.

Prepared source consumer `pipeline/native_range_shape_file.py` validates original
size/SHA/MD5 before reading identity/shape columns via one file descriptor.
`pipeline/native_range_shapes.py` retains nulls and admits complete native key
order/counts. Independent `pipeline/native_range_shape_reference.py` rereads
original metadata without extractor reuse. Live engineering integration verifies
all3,970 records in both retained scenes; source mutations and rehashed output
mutations are refused by targeted live fixtures. Receipts:
`research/native-shape-file-integration-verified.json` and
`research/native-shape-reference-integration-verified.json`.

The full recovery plan is `docs/superpowers/plans/2026-10-01-native-range-shape-recovery.md`
(repository-relative). Actual103-scene HDFS staging, record-by-record independent
replay, archive-to-shape linkage, pixel bounds and full split reconciliation remain
open. Serial shape execution follows processing, box replay and semantic recovery
under the shared queue/raw leases. These engineering checks neither clear ticket07
nor constitute RSN training, a scientific comparison, or a model adoption decision.
