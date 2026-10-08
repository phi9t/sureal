# 09 — Verify TF-free Perception evaluation

**Goal / what to deliver:** Score detection and semantic predictions under pinned native definitions without TensorFlow.

**Blocked by:** [06](06-r0-closeout.md)

**Status:** verified-complete — current native evaluator/export evidence and resource reports independently reconciled

**Lane:** core

**Verifier:** Build/audit the evaluator dependency closure and run live hand-checkable perfect, empty, wrong-class, ignored-label and localization fixtures against pinned reference expectations.

## Acceptance criteria

- [x] Detection AP/APH and point-IoU configurations, class namespaces and export schema are pinned.
- [x] Fixture expected values and numeric tolerances are independently derived or tied to pinned authoritative fixtures.
- [x] Transitive build/runtime dependencies contain no TensorFlow; failed parity blocks benchmark-compatible claims.
- [x] Missing annotations and annotated-empty examples receive distinct coverage handling.
- [x] Camera segmentation scoring has audited class mapping and eligible-pixel denominators; temporal panoptic parity is a later gate if adopted.
- [x] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [x] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

## Current evidence

Implemented metric settings, source hashes and separate box/LiDAR/camera class namespaces are pinned in [contracts.json](../../../experiments/waymo-perception/evaluation/contracts.json). Native detection fixtures include a paired NLZ suppression control; segmentation fixtures cover ignored/undefined/absent classes. Full engineering-source semantic exports and native boxes were independently decoded and reconciled with source points/Parquet. [Camera evidence](../../../experiments/waymo-perception/research/real-camera-semantic-verified.json) reconciles all 990 labeled images, 995 missing annotations and 2,133,338,748 eligible pixels. Camera scoring is an explicitly declared semantic diagnostic; official panoptic/STQ parity is outside this gate. Final consolidated current-code/runtime/dependency and resource evidence is still required before closure. Cross-modal ontology mapping belongs to the separately frozen mask-transfer protocol and must not equate raw IDs.

## Verified closeout

[Independent gate evidence](../../../experiments/waymo-perception/research/perception-evaluators-verified.json) maps all seven acceptance criteria to verified sources, fixtures, live receipts and measured resources. Consolidated replay: `python3 experiments/waymo-perception/evaluation/audit-perception-gate.py <fresh-output-directory>`; linked receipts retain individual exact commands. Scope is default native upright-3D detection AP/APH, native TOP point-semantic IoU and explicitly declared camera semantic diagnostics. Camera 2D/LET configurations and official temporal panoptic/STQ parity require separate live gates before their respective experiments. Cross-modal ontology mapping remains in scientific preregistration. Ground-truth self-replay carries no model performance claim.
