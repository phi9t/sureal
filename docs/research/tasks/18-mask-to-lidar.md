# 18 — Test geometry-aware mask transfer

**Goal / what to deliver:** Determine whether refined masks improve native point-semantic support beyond box-based transfer.

**Blocked by:** [17](17-sam-mask-refinement.md), [11](11-point-segmentation.md), [04](04-sensor-reconstruction.md)

**Status:** planned — blocked by prerequisite verification

**Lane:** core

**Verifier:** Live B0/B1/B2 transfer using identical calibrated projection and visibility rules; independent original-point identity checks and paired held-out mIoU analysis.

## Acceptance criteria

- [ ] Measured LiDAR defines the multimodal condition; masks alone are not claimed to supply metric depth.
- [ ] Behind-surface, overlapping and unsupported associations remain unknown with reasons; all original points remain represented.
- [ ] Primary paired point-mIoU change uses identical eligible support; coverage/conflict and distance/occlusion diagnostics are published.
- [ ] Report 95% segment-level intervals and end-to-end cost; promotion requires positive lower interval bound under the preregistered resource cap.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

## Pending semantic evidence contract

[Candidate semantic provenance](../../../experiments/waymo-perception/research/mask-semantic-provenance-candidate.md) addresses the coarse detector/fine segmentation mismatch. Predicted camera semantic evidence must be held identical across box/SAM/SAM 3 supports; ambiguous mappings abstain while a common independent LiDAR prediction retains full native point support. Mapping, pooling and fallback remain candidate decisions under ticket 07; this note is not task closure.

[Live support-association fixtures](../../../experiments/waymo-perception/research/mask-point-support-verified.json) verify native pixel sampling with allpoints retained, explicit external visibility and conflict abstentions. This prepares a shared B0/B1/B2 association layer; calibrated visibility, actualpredicted camera/SAM provenance, realinputintegration and scientificfreeze/heldoutcomparisons remain open.

Current association candidate uses [normalization regression evidence](../../../experiments/waymo-perception/research/mask-point-support-normalization-verified.json): boolean array-like masks are consistently normalized without caller mutation, after reproduced live failure; all five fixture groups pass. Earlier receipt remains historical for its original candidate.

Measured visibility preparation: research/projection-visibility-verified.json records3 live Insula fixture groups for a sparse native-pixel depth-frontier estimator. Both projection slots and every original point are retained; camera availability, image bounds, invalid forward depth and behind-measured-surface reasons remain explicit. Only points projecting to the identical camera/pixel compete; there is no dilation or dense free-space inference. Forward depth must come from independently validated camera-axis/exposure-time geometry. Tolerance is an explicit candidate parameter requiring preregistration. Native calibrated/timing integration, unmeasured occlusion and held-out SAM comparisons remain open.

Untyped native teacher relation preparation: `research/sam-point-relation-native-verified.json` records original-point-order association of actual frozen SAM masks with all157,870 TOP/both-return native projections in the matching engineering frame. Literal two-slot pixel lookup independently agrees for every point/mask relation. Oracle prompt origin is retained; no camera semantic class or panoptic identity is invented from box classes. Without calibrated exposure-time visibility, all visible support remains unpromoted. This accepts projection-incidence plumbing only; visibility, predicted masks, semantic supervision strategy and scientific comparisons remain open.

Observed engineering coverage limit: all21,234 front-camera-projectable native TOP points miss the initial three tiny oracle masks (160/258/618 image pixels). `research/sam-point-relation-native-lineage-verified.json` pins teacher and relation receipts/artifacts. Zero point support must remain zero; this fixture cannot demonstrate useful semantic distillation. Expand the engineering diagnostic to all annotated camera prompts in the frame rather than selecting masks by favorable model outcomes. Scientific experiments still require predicted-box prompts and full held-out eligibility/visibility accounting.

Whole-frame engineering oracle coverage: `research/sam-full-frame-independent-verified.json` admits all63 source-ordered prompts, exact native mask restoration in two-mask CPU chunks, and literal point relations. `research/sam-full-frame-coverage.json` records26 masks with projected TOP support and37 with none;1486 unique points lie in any mask, with47 in overlapping masks. No oracle prompt is removed for poor output/support. All visibility-qualified support remains unpromoted. Predicted-box native quality, calibrated timing/visibility and scientific held-out comparisons remain open.

Exposure-time camera-core preparation: `research/camera-core-native-lineage-verified.json` records ten unchanged upstream camera-model tests compiled/executed live against pinned Waymo commit99a4cb3 and standalone Eigen3.4.0 headers. Rolling/global shutter, moving-point depth, behind-camera handling and principal-point timing tests pass. The original source/test/include headers, Eigen headers, binary/report/log and shared-library dependencies were verified. No TensorFlow dependency is linked or installed; locked C++ runtime content was freshly checked. Actual Perception-v2 calibration/image/pose bridging, native projection/depth parity, measurement versus moving-object assumptions and visibility policy remain open.

Native Perception-v2 camera bridge: `research/camera-native-projection-executed.json` pins an offline C++ run over all157,870 reconstructed world points, native calibration/image/vehicle-pose rows and shutter fields. Two adapter groups and ten upstream tests pass live. `research/camera-native-projection-residuals.json` compares21,234 supplied FRONT correspondences: all have positive forward depth and valid native-core output, but pixel L2 median1.294,p95=2.790,max=3.721. Only9,372 agree within1px per axis. Do not promote these residuals as exact projection parity or visibility certification. Static-world point motion is explicit; schema global-angular wording conflicts with core body-angular treatment. Investigate shutter conventions, upstream projection generation and native motion semantics before freezing the visibility policy.

### 2026-10-01 camera convention isolation

Live offline Insula diagnostic `research/camera-convention-diagnostic-verified.json`
reprojects all 157,870 original points, comparing all 21,234 supplied FRONT slots
without changing the production bridge. The unchanged native baseline reproduces
prior residuals exactly. Global shutter increases median/p95 L2 residual from
1.294/2.790 to 1.546/4.855 pixels. Converting the schema-described global angular
velocity into vehicle coordinates yields 1.293/2.785 pixels: insufficient to
explain the discrepancy. All compared points remain valid with positive depth.
The diagnostic receipt and all retained artifacts were rehashed; both native C++
and NumPy audit executed in offline Insula, with runtime content checked.

Neither diagnostic establishes the supplied projection generation convention or
physical visibility. Preserve native metadata in the production bridge. Next
investigate supplied integer projection generation/quantization and systematic
range/scan-position residual structure; actor-motion assumptions remain explicit.
Visibility-qualified support and semantic pseudo-label promotion remain gated.

Live residual structure diagnostic now distinguishes final integer rounding from
remaining geometry error: flooring matches 4,875/21,234 slots; 16,359 slots are
outside the floor unit square. Source-grounded analysis and implications are in
`research/camera-projection-residual-investigation.md`. Upstream range-image
rounding is a plausible explanation consistent with measured scale, not a proven
per-frame error decomposition. No fitted correction or visibility promotion.

### Native sparse-depth frontier integration

`research/native-measured-visibility-verified.json` records a live offline Insula
run joining all157,870 original points, native FRONT slots, static-world camera
core forward depths, and all63 frozen SAM masks. An independently sorted
pixel/depth frontier agrees for every original slot at explicit diagnostic
0/0.1/0.5/1.0m tolerances. All315,740 slot reasons are accounted for; unavailable
cameras remain unavailable. Worker elapsed3.394s, peakRSS284,116KiB. Source teacher
and projection receipts/artifacts and current candidate code were rehashed.

There are21,234 valid FRONT slots but20,968 distinct pixels. All four tolerances
retain20,968 nearest-measured slots and exclude266 behind-measured slots. Mask
incidence has1,486 original points; sparse-nearest mask incidence has1,479.
These labels mean only nearest among measurements at the identical native pixel.
The high singleton rate makes this rule insufficient to certify general physical
visibility or unmeasured occlusion. It must not silently satisfy the ticket's
behind-surface/unsupported-association acceptance criterion. Engineering oracle
prompts, approximate static-world depth, mask-boundary uncertainty and unavailable
other-camera depths remain explicit. No semantic labels are assigned or support
promoted; scientific tolerance freeze remains open.

### Boundary uncertainty diagnostic

`research/sam-boundary-support-verified.json` records all63 frozen oracle-prompt
SAM masks and all157,870 original points in a live offline CPU Insula run. A
square neighborhood must be entirely inside the mask; outside-image neighborhoods
abstain. Integral-image decisions match an independent shifted-pixel lookup for
every native FRONT slot and every mask at radii0/1/3/5pixels. Larger radii are
verified subsets, never new support. Radius0 exactly reproduces1,486 unique
associated points,26 supported masks and47 overlapping points. Radius1 retains
1,396 points/25 masks; radius3 retains1,206/20; radius5 retains1,038/14. Worker
elapsed3.133s, peakRSS237,708KiB; receipt/artifact identities were rehashed.

This quantifies engineering sensitivity to mask boundaries, not a calibrated
projection-error bound, physical visibility, trained semantic support or a
scientific radius selection. All four candidate radii remain diagnostics; freeze
requires training/development multi-frame/camera evidence and common rules across
B0/B1/B2. Do not tune radii from held-out outcomes or remove zero-support masks.
